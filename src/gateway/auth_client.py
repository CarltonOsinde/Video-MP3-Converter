"""Thin HTTP client for the auth service.

Each function returns (result, error) where error is None or (message, status).
"""

import os

import requests

TIMEOUT_SECONDS = 5


def _auth_url(path):
    return f"http://{os.environ['AUTH_SVC_ADDRESS']}{path}"


def login(authorization):
    if not authorization or not authorization.username or not authorization.password:
        return None, ("missing credentials", 401)

    try:
        response = requests.post(
            _auth_url("/login"),
            auth=(authorization.username, authorization.password),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None, ("auth service unavailable", 503)

    if response.status_code == 200:
        return response.text, None
    return None, ("invalid credentials", response.status_code)


def validate(authorization_header):
    """Return (claims, None) for a valid bearer token, else (None, error)."""
    if not authorization_header:
        return None, ("missing credentials", 401)

    try:
        response = requests.post(
            _auth_url("/validate"),
            headers={"Authorization": authorization_header},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None, ("auth service unavailable", 503)

    if response.status_code == 200:
        return response.json(), None
    return None, ("invalid or expired token", 401)
