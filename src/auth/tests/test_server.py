import base64
import datetime
import os
import sys
import types
import unittest
from unittest import mock

# pymysql is only needed when talking to a real database; stub it for tests.
sys.modules.setdefault("pymysql", types.SimpleNamespace(connect=None, cursors=types.SimpleNamespace(DictCursor=None)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import server  # noqa: E402

SECRET = "test-secret-that-is-at-least-32-bytes"
USER = {"email": "user@example.com", "password_hash": generate_password_hash("correct-horse"), "is_admin": 0}


def basic(email, password):
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@mock.patch.dict(os.environ, {"JWT_SECRET": SECRET})
class AuthServiceTest(unittest.TestCase):
    def setUp(self):
        self.client = server.server.test_client()

    def test_login_requires_credentials(self):
        self.assertEqual(self.client.post("/login").status_code, 401)

    @mock.patch.object(server, "get_user", return_value=USER)
    def test_login_returns_valid_jwt(self, _):
        response = self.client.post("/login", headers=basic("user@example.com", "correct-horse"))
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(response.get_data(as_text=True), SECRET, algorithms=["HS256"])
        self.assertEqual(claims["username"], "user@example.com")
        self.assertFalse(claims["admin"])

    @mock.patch.object(server, "get_user", return_value=USER)
    def test_login_rejects_wrong_password(self, _):
        response = self.client.post("/login", headers=basic("user@example.com", "wrong"))
        self.assertEqual(response.status_code, 401)

    @mock.patch.object(server, "get_user", return_value=None)
    def test_login_rejects_unknown_user(self, _):
        response = self.client.post("/login", headers=basic("nobody@example.com", "whatever"))
        self.assertEqual(response.status_code, 401)

    def test_validate_accepts_fresh_token(self):
        token = server.create_jwt("user@example.com", SECRET, True)
        response = self.client.post("/validate", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["admin"])

    def test_validate_rejects_expired_token(self):
        long_ago = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=2)
        token = server.create_jwt("user@example.com", SECRET, False, now=long_ago)
        response = self.client.post("/validate", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_validate_rejects_token_signed_with_other_secret(self):
        token = server.create_jwt("user@example.com", "another-secret-that-is-at-least-32-bytes", False)
        response = self.client.post("/validate", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_validate_requires_bearer_scheme(self):
        response = self.client.post("/validate", headers={"Authorization": "Basic abc"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
