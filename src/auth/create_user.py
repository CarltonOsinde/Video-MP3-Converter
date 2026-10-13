"""Create a user for the auth service, storing only a salted password hash.

Usage (with the same MYSQL_* environment variables as the service):
    python create_user.py you@example.com            # prompts for a password
    python create_user.py you@example.com --admin
"""

import argparse
import getpass
import os

import pymysql
from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters")

    connection = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"],
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO user (email, password_hash, is_admin) VALUES (%s, %s, %s)",
            (args.email, generate_password_hash(password), args.admin),
        )
        connection.commit()
    print(f"Created user {args.email}")


if __name__ == "__main__":
    main()
