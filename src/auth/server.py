import jwt, datetime, os #JWT (JSON Web Tokens) ~ used for our auth, datetime ~ expiration date on our token and os ~ use enviroment varialbles to connect our SQL connection
from flask import Flask,request #Used to create the Server
from flask_mysqldb import MySQL #Used to query the databases


#Instanstiation of Flask & MYSQL objects
server = Flask(__name__)
mysql = MySQL(server)


#config
server.config ["MySQL_HOST"] = os.environ.get("MYSQL_HOST")
server.config["MYSQL_USER"] = os.environ.get("MYSQL_USER")
server.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD")
server.config["MYSQL_DB"] = os.environ.get("MYSQL_DB")
server.config["MYSQL_PORT"] = os.environ.get("MYSQL_PORT")

#Routes
@server.route("/login", methods = ["POST"])

def login():
        auth = request.authorization
        if not auth:
            return "missing credentials", 401

        #Check DB for username and password
         