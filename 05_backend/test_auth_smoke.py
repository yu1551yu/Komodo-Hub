import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from auth.handlers import handle_login
from models.user_repository import seed_users_if_empty

seed_users_if_empty()
s, _, _ = handle_login({"email": "student@komodo.id", "password": "wrong"})
assert s == 401, s
s, body, token = handle_login({"email": "student@komodo.id", "password": "demo123"})
assert s == 200 and token, (s, body)
print("auth smoke tests passed")
