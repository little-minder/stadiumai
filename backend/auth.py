"""
Lightweight authentication layer.

This is intentionally simple (no password hashing / real credential store)
since the goal is to *identify who used the site* for a live-ops demo -
username + email + login time, per the brief - not to build a production
auth system. Swap in a real provider (e.g. Auth0, Firebase Auth, or your
own bcrypt+JWT stack) by replacing `login()` while keeping the same
response shape ({token, username, email, login_time}).
"""
import secrets
import threading
from datetime import datetime

_lock = threading.Lock()

# token -> user record
SESSIONS = {}
# full login history, most recent first (what the organizer dashboard shows)
LOGIN_LOG = []


def login(username, email):
    username = (username or "").strip()
    email = (email or "").strip()
    if not username:
        return None
    token = secrets.token_hex(16)
    record = {
        "token": token,
        "username": username,
        "email": email or "not provided",
        "login_time": datetime.utcnow().isoformat(),
    }
    with _lock:
        SESSIONS[token] = record
        LOGIN_LOG.insert(0, {k: v for k, v in record.items() if k != "token"})
    return record


def resolve(token):
    with _lock:
        return SESSIONS.get(token)


def recent_logins(limit=25):
    with _lock:
        return list(LOGIN_LOG[:limit])


def username_for_token(token):
    rec = resolve(token)
    return rec["username"] if rec else "Guest"
