from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ITERATIONS = 100_000


def hash_password(plain: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        algo, iter_s, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
