"""Sign-up / sign-in logic.

* Passwords are never stored - only a PBKDF2-HMAC-SHA256 hash with a random
  per-user salt (200k iterations).
* Accounts lock for 10 minutes after 5 consecutive failed sign-ins.
* Sign-in errors are deliberately generic so they do not reveal which emails
  are registered.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import auth
import db
import portfolio

ITERATIONS = 200_000
MAX_ATTEMPTS = 5
LOCK_MINUTES = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC_ERROR = "Incorrect email or password."


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), ITERATIONS
    ).hex()


def _public(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "created_at": user["created_at"],
    }


def password_issues(password: str) -> list[str]:
    issues = []
    if len(password) < 8:
        issues.append("at least 8 characters")
    if not re.search(r"[A-Za-z]", password):
        issues.append("a letter")
    if not re.search(r"\d", password):
        issues.append("a number")
    return issues


def signup(full_name: str, email: str, password: str, confirm: str) -> tuple[Optional[dict], str]:
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if len(full_name) < 2:
        return None, "Enter your full name."
    if not EMAIL_RE.match(email):
        return None, "Enter a valid email address."
    issues = password_issues(password or "")
    if issues:
        return None, "Your password needs " + ", ".join(issues) + "."
    if password != confirm:
        return None, "The two passwords do not match."

    salt = secrets.token_hex(16)
    user_id = db.create_user(full_name, email, _hash_password(password, salt), salt)
    if user_id is None:
        return None, "An account with this email already exists. Sign in instead."
    return _public(db.get_user_by_id(user_id)), "Account created."


def login(email: str, password: str) -> tuple[Optional[dict], str]:
    email = (email or "").strip().lower()
    user = db.get_user_by_email(email)
    if user is None:
        _hash_password(password or "", "00" * 16)  # keep timing similar
        return None, GENERIC_ERROR

    if user["locked_until"]:
        locked_until = datetime.fromisoformat(user["locked_until"])
        if datetime.now(timezone.utc) < locked_until:
            return None, f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes."

    candidate = _hash_password(password or "", user["salt"])
    if hmac.compare_digest(candidate, user["password_hash"]):
        db.set_login_state(user["id"], 0, None)
        return _public(user), "Welcome back."

    failed = user["failed_attempts"] + 1
    if failed >= MAX_ATTEMPTS:
        until = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)).isoformat()
        db.set_login_state(user["id"], 0, until)
        return None, f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes."
    db.set_login_state(user["id"], failed, None)
    return None, GENERIC_ERROR


def change_password(user_id: int, current: str, new: str, confirm: str) -> tuple[bool, str]:
    user = db.get_user_by_id(user_id)
    if user is None:
        return False, "Account not found."
    if not hmac.compare_digest(_hash_password(current or "", user["salt"]), user["password_hash"]):
        return False, "Your current password is incorrect."
    issues = password_issues(new or "")
    if issues:
        return False, "Your new password needs " + ", ".join(issues) + "."
    if new != confirm:
        return False, "The two new passwords do not match."
    salt = secrets.token_hex(16)
    db.update_password(user_id, _hash_password(new, salt), salt)
    return True, "Password updated."
