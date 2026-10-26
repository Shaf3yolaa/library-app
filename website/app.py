import os
import uuid
from decimal import Decimal

import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "super-secret-key")
bcrypt = Bcrypt(app)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

def get_library_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database="library",
        cursorclass=pymysql.cursors.DictCursor,
    )


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def save_image(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_image(file_storage.filename):
        return None, "Please upload a PNG, JPG, JPEG, WEBP, or GIF image."
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_IMAGE_SIZE:
        return None, "Image size must be 5 MB or less."

    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(app.static_folder, "uploads", folder)
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return f"uploads/{folder}/{filename}", None


def delete_image(image_path):
    if not image_path:
        return
    safe_path = os.path.normpath(image_path).replace("\\", "/")
    if safe_path.startswith("uploads/"):
        full_path = os.path.join(app.static_folder, safe_path)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
            except OSError:
                pass


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("library"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form = {"name": "", "email": "", "password": "", "confirm_password": ""}
    if request.method == "POST":
        form = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "password": request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
        }

        error = None
        if not form["name"]:
            error = "Name is required"
        elif not form["email"]:
            error = "Email is required"
        elif not form["password"]:
            error = "Password is required"
        elif not form["confirm_password"]:
            error = "Confirm password is required"
        elif form["password"] != form["confirm_password"]:
            error = "Passwords do not match"

        if error:
            flash(error, "error")
            return render_template("register.html", form=form)

        pw_hash = bcrypt.generate_password_hash(form["password"]).decode("utf-8")
        conn = get_library_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s);",
                    (form["email"], form["name"], pw_hash),
                )
                user_id = cursor.lastrowid
            conn.commit()
            session["user_id"] = user_id
            session["name"] = form["name"]
            return redirect(url_for("library"))
        except pymysql.err.IntegrityError:
            conn.rollback()
            flash("Email already exists", "error")
            return render_template("register.html", form=form)
        finally:
            conn.close()

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email:
            flash("Email is required", "error")
        elif not password:
            flash("Password is required", "error")
        else:
            conn = get_library_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id, name, password_hash FROM users WHERE email = %s;", (email,))
                    user = cursor.fetchone()
                if user and bcrypt.check_password_hash(user["password_hash"], password):
                    session["user_id"] = user["user_id"]
                    session["name"] = user["name"]
                    return redirect(url_for("library"))
                flash("Invalid email or password", "error")
            finally:
                conn.close()
    return render_template("login.html", email=email)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/library")
def library():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_library_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM AUTHOR ORDER BY name;")
            authors = cursor.fetchall()
            cursor.execute("SELECT BOOK.*, AUTHOR.name AS author_name FROM BOOK JOIN AUTHOR ON BOOK.author_id = AUTHOR.author_id ORDER BY title;")
            books = cursor.fetchall()
    finally:
        conn.close()
    return render_template("library.html", authors=authors, books=books)


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    if "user_id" not in session:
        return redirect(url_for("login"))
    form = {"name": "", "country": ""}
    if request.method == "POST":
        form = {"name": request.form.get("name", "").strip(), "country": request.form.get("country", "").strip()}
        image_path, image_error = save_image(request.files.get("image"), "authors")
        if not form["name"] or not form["country"]:
            if image_path: delete_image(image_path)
            flash("Please complete all author fields.", "error")
            return render_template("add_author.html", form=form)
        if image_error:
            flash(image_error, "error")
            return render_template("add_author.html", form=form)
        conn = get_library_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO AUTHOR (name, country, image_path) VALUES (%s, %s, %s);", (form["name"], form["country"], image_path))
            conn.commit()
        finally:
            conn.close()
        flash("Author added successfully!", "success")
        return redirect(url_for("library"))
    return render_template("add_author.html", form=form)


@app.route("/edit_author/<int:author_id>", methods=["GET", "POST"])
def edit_author(author_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_library_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM AUTHOR WHERE author_id = %s;", (author_id,))
            author = cursor.fetchone()
        if not author:
            flash("Author not found.", "error")
            return redirect(url_for("library"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            country = request.form.get("country", "").strip()
            new_image, image_error = save_image(request.files.get("image"), "authors")
            if not name or not country:
                if new_image: delete_image(new_image)
                flash("Please complete all author fields.", "error")
                return render_template("edit_author.html", author={**author, "name": name, "country": country})
            if image_error:
                flash(image_error, "error")
                return render_template("edit_author.html", author={**author, "name": name, "country": country})
            image_path = new_image if new_image else author.get("image_path")
            with conn.cursor() as cursor:
                cursor.execute("UPDATE AUTHOR SET name=%s, country=%s, image_path=%s WHERE author_id=%s;", (name, country, image_path, author_id))
            conn.commit()
            if new_image and author.get("image_path"):
                delete_image(author["image_path"])
            flash("Author updated successfully!", "success")
            return redirect(url_for("library"))
    finally:
        conn.close()
    return render_template("edit_author.html", author=author)


@app.route("/delete_author/<int:author_id>", methods=["POST"])
def delete_author(author_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_library_db_connection()
    image_paths = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT image_path FROM AUTHOR WHERE author_id=%s;", (author_id,))
            author = cursor.fetchone()
            cursor.execute("SELECT image_path FROM BOOK WHERE author_id=%s;", (author_id,))
            image_paths = [r["image_path"] for r in cursor.fetchall()]
            if author: image_paths.append(author.get("image_path"))
            cursor.execute("DELETE FROM AUTHOR WHERE author_id = %s;", (author_id,))
        conn.commit()
    finally:
        conn.close()
    for path in image_paths: delete_image(path)
    flash("Author and associated books deleted successfully!", "success")
    return redirect(url_for("library"))


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if "user_id" not in session:
        return redirect(url_for("login"))
    form = {"title": "", "price": "", "author_id": ""}
    conn = get_library_db_connection()
    try:
        if request.method == "POST":
            form = {"title": request.form.get("title", "").strip(), "price": request.form.get("price", "").strip(), "author_id": request.form.get("author_id", "")}
            image_path, image_error = save_image(request.files.get("image"), "books")
            if not form["title"] or not form["price"] or not form["author_id"]:
                if image_path: delete_image(image_path)
                flash("Please complete all book fields.", "error")
                with conn.cursor() as cursor: cursor.execute("SELECT * FROM AUTHOR ORDER BY name;"); authors = cursor.fetchall()
                return render_template("add_book.html", authors=authors, form=form)
            if image_error:
                flash(image_error, "error")
                with conn.cursor() as cursor: cursor.execute("SELECT * FROM AUTHOR ORDER BY name;"); authors = cursor.fetchall()
                return render_template("add_book.html", authors=authors, form=form)
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO BOOK (title, price, author_id, image_path) VALUES (%s, %s, %s, %s);", (form["title"], form["price"], form["author_id"], image_path))
            conn.commit()
            flash("Book added successfully!", "success")
            return redirect(url_for("library"))
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM AUTHOR ORDER BY name;")
            authors = cursor.fetchall()
    finally:
        conn.close()
    return render_template("add_book.html", authors=authors, form=form)


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_library_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM BOOK WHERE book_id = %s;", (book_id,))
            book = cursor.fetchone()
            cursor.execute("SELECT * FROM AUTHOR ORDER BY name;")
            authors = cursor.fetchall()
        if not book:
            flash("Book not found.", "error")
            return redirect(url_for("library"))
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            price = request.form.get("price", "").strip()
            author_id = request.form.get("author_id", "")
            new_image, image_error = save_image(request.files.get("image"), "books")
            if not title or not price or not author_id:
                if new_image: delete_image(new_image)
                flash("Please complete all book fields.", "error")
                return render_template("edit_book.html", book={**book, "title": title, "price": price, "author_id": author_id}, authors=authors)
            if image_error:
                flash(image_error, "error")
                return render_template("edit_book.html", book={**book, "title": title, "price": price, "author_id": author_id}, authors=authors)
            image_path = new_image if new_image else book.get("image_path")
            with conn.cursor() as cursor:
                cursor.execute("UPDATE BOOK SET title=%s, price=%s, author_id=%s, image_path=%s WHERE book_id=%s;", (title, price, author_id, image_path, book_id))
            conn.commit()
            if new_image and book.get("image_path"):
                delete_image(book["image_path"])
            flash("Book updated successfully!", "success")
            return redirect(url_for("library"))
    finally:
        conn.close()
    return render_template("edit_book.html", book=book, authors=authors)


@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_library_db_connection()
    image_path = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT image_path FROM BOOK WHERE book_id=%s;", (book_id,))
            book = cursor.fetchone()
            image_path = book.get("image_path") if book else None
            cursor.execute("DELETE FROM BOOK WHERE book_id = %s;", (book_id,))
        conn.commit()
    finally:
        conn.close()
    delete_image(image_path)
    flash("Book removed successfully!", "success")
    return redirect(url_for("library"))


if __name__ == "__main__":
    app.run(debug=True)
