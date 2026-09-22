import time
from collections import defaultdict, deque

import bcrypt


MAX_PASSWORD_BYTES = 72
MAX_LOGIN_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))


def login_allowed(identifier: str) -> bool:
    now = time.time()
    failures = _failed_logins[identifier.lower()]
    while failures and now - failures[0] > LOGIN_WINDOW_SECONDS:
        failures.popleft()
    return len(failures) < MAX_LOGIN_FAILURES


def record_login_failure(identifier: str) -> None:
    _failed_logins[identifier.lower()].append(time.time())


def clear_login_failures(identifier: str) -> None:
    _failed_logins.pop(identifier.lower(), None)