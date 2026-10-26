DROP DATABASE IF EXISTS library;
CREATE DATABASE library;
USE library;

CREATE TABLE users (
    user_id           INT          NOT NULL AUTO_INCREMENT,
    email             VARCHAR(255) NOT NULL,
    name              VARCHAR(100) NOT NULL,
    password_hash     VARCHAR(255) NOT NULL,
    registration_date TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    UNIQUE (email)
);

CREATE TABLE AUTHOR (
    author_id INT          NOT NULL AUTO_INCREMENT,
    name      VARCHAR(100) NOT NULL,
    country   VARCHAR(100) NOT NULL,
    PRIMARY KEY (author_id)
);

CREATE TABLE BOOK (
    book_id   INT            NOT NULL AUTO_INCREMENT,
    title     VARCHAR(150)   NOT NULL,
    price     DECIMAL(10,2)  NOT NULL,
    author_id INT            NOT NULL,
    PRIMARY KEY (book_id)
);

ALTER TABLE BOOK ADD FOREIGN KEY (author_id) REFERENCES AUTHOR(author_id) ON DELETE CASCADE;
ALTER TABLE AUTHOR ADD COLUMN image_path VARCHAR(255) NULL;
ALTER TABLE BOOK ADD COLUMN image_path VARCHAR(255) NULL;
