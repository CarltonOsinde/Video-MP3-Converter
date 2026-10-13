"""Auth service: verifies user credentials against MySQL and issues/validates JWTs.

Endpoints
    POST /login     HTTP Basic auth (email + password)  -> 200 JWT | 401
    POST /validate  Authorization: Bearer <JWT>         -> 200 claims | 401
    GET  /health                                        -> 200
"""

import datetime
import os

import jwt
import pymysql
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash

TOKEN_TTL = datetime.timedelta(hours=24)
JWT_ALGORITHM = "HS256"

server = Flask(__name__)


def get_user(email):
    """Return {"email", "password_hash", "is_admin"} for the user, or None."""
    connection = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            # Parameterised query: the driver escapes the value, preventing SQL injection.
            cursor.execute(
                "SELECT email, password_hash, is_admin FROM user WHERE email = %s",
                (email,),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def create_jwt(email, secret, is_admin, now=None):
    now = now or datetime.datetime.now(tz=datetime.timezone.utc)
    claims = {
        "username": email,
        "admin": bool(is_admin),
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


@server.post("/login")
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return jsonify(message="missing credentials"), 401

    user = get_user(auth.username)
    # Same response for unknown user and wrong password, so the endpoint
    # doesn't reveal which emails are registered.
    if not user or not check_password_hash(user["password_hash"], auth.password):
        return jsonify(message="invalid credentials"), 401

    token = create_jwt(user["email"], os.environ["JWT_SECRET"], user["is_admin"])
    return token, 200


@server.post("/validate")
def validate():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return jsonify(message="missing bearer token"), 401

    try:
        claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify(message="token expired"), 401
    except jwt.InvalidTokenError:
        return jsonify(message="invalid token"), 401

    return jsonify(claims), 200


@server.get("/health")
def health():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
