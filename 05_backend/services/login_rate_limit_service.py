"""Server-side policy for limiting repeated failed authentication attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import os
import secrets
from threading import RLock


# An account is protected aggressively against credential stuffing, while the
# broader IP threshold is higher to avoid locking a whole school/NAT after a few
# pupils mistype different passwords.
MAX_ACCOUNT_FAILURES = 5
MAX_IP_FAILURES = 20
LOCKOUT = timedelta(minutes=5)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(frozen=True)
class AttemptState:
    failure_count: int = 0
    locked_until: datetime | None = None


class InMemoryLoginRateLimitStore:
    """Thread-safe local state for the single-process course-project server."""

    def __init__(self):
        self._rows: dict[tuple[str, str], AttemptState] = {}
        self._lock = RLock()

    def get_attempt(self, scope: str, subject_fingerprint: str) -> AttemptState | None:
        with self._lock:
            return self._rows.get((scope, subject_fingerprint))

    def increment_failure(self, scope: str, subject_fingerprint: str, threshold: int, lockout: timedelta) -> datetime | None:
        with self._lock:
            previous = self._rows.get((scope, subject_fingerprint), AttemptState())
            count = previous.failure_count + 1
            locked_until = _now() + lockout if count >= threshold else None
            self._rows[(scope, subject_fingerprint)] = AttemptState(count, locked_until)
            return locked_until

    def clear_attempt(self, scope: str, subject_fingerprint: str) -> None:
        with self._lock:
            self._rows.pop((scope, subject_fingerprint), None)


STORE = InMemoryLoginRateLimitStore()
LOGGER = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_pepper(configured_value: str | None) -> bytes:
    """Use configured secret when supplied, otherwise a safe process-local one."""
    value = (configured_value or "").strip()
    if len(value) >= 32:
        return value.encode("utf-8")
    return secrets.token_urlsafe(48).encode("utf-8")


# Local course-project runs require no setup. The value lasts only for this
# server process and is never logged or written to disk. Production deployments
# should configure LOGIN_RATE_LIMIT_PEPPER so separate instances share a stable
# fingerprint secret.
PROCESS_PEPPER = _resolve_pepper(os.getenv("LOGIN_RATE_LIMIT_PEPPER"))


def _pepper() -> bytes:
    return PROCESS_PEPPER


def _fingerprints(email: str, remote_addr: str) -> tuple[str, str]:
    key = _pepper()
    email_fingerprint = hmac.new(key, email.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
    ip_fingerprint = hmac.new(key, remote_addr.strip().encode("utf-8"), hashlib.sha256).hexdigest()
    return email_fingerprint, ip_fingerprint


def _subjects(email: str, remote_addr: str) -> tuple[tuple[str, str], tuple[str, str], str, str]:
    email_fingerprint, ip_fingerprint = _fingerprints(email, remote_addr)
    return ("ACCOUNT", email_fingerprint), ("IP", ip_fingerprint), email_fingerprint, ip_fingerprint


def check(email: str, remote_addr: str, store: InMemoryLoginRateLimitStore | None = None) -> RateLimitResult:
    store = store or STORE
    account, ip, email_fingerprint, ip_fingerprint = _subjects(email, remote_addr)
    longest_wait = 0
    for scope, subject_fingerprint in (account, ip):
        row = store.get_attempt(scope, subject_fingerprint)
        if not row or not row.locked_until:
            continue
        locked_until = row.locked_until
        remaining = int((locked_until - _now()).total_seconds())
        if remaining > 0:
            longest_wait = max(longest_wait, remaining)
        else:
            store.clear_attempt(scope, subject_fingerprint)
            LOGGER.info("login_lock_expired")
    if longest_wait:
        return RateLimitResult(False, longest_wait)
    return RateLimitResult(True)


def record_failure(email: str, remote_addr: str, store: InMemoryLoginRateLimitStore | None = None) -> RateLimitResult:
    store = store or STORE
    account, ip, _, _ = _subjects(email, remote_addr)
    longest_wait = 0
    for scope, subject_fingerprint in (account, ip):
        threshold = MAX_ACCOUNT_FAILURES if scope == "ACCOUNT" else MAX_IP_FAILURES
        locked_until = store.increment_failure(scope, subject_fingerprint, threshold, LOCKOUT)
        if locked_until:
            longest_wait = max(longest_wait, int(LOCKOUT.total_seconds()))
    LOGGER.warning("login_locked" if longest_wait else "login_failed")
    return RateLimitResult(not bool(longest_wait), longest_wait)


def record_success(email: str, remote_addr: str, store: InMemoryLoginRateLimitStore | None = None) -> None:
    store = store or STORE
    account, _, _, _ = _subjects(email, remote_addr)
    store.clear_attempt(account[0], account[1])
    LOGGER.info("login_success_cleared")
