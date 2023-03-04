CREATE USER 'auth_user' @ 'localhost' IDENTIFIED BY 'Aauth123';

CREATE DATABASE auth;

GRANT ALL PRIVILEGES ON auth.* TO 'auth_user'@'localhost';


USE auth;

CREATE TABLE user (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR (255) NOT NULL,
    password VARCHAR(255) NOT NULL

);

INSERT INTO user (email,password) VALUES ('carltonosinde@gmail.com', 'Admin123');


