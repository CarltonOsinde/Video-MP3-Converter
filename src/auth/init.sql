-- Schema for the auth service. Create users with create_user.py so that
-- passwords are only ever stored as salted hashes.

CREATE DATABASE IF NOT EXISTS auth;
USE auth;

CREATE TABLE IF NOT EXISTS user (
    id            INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
