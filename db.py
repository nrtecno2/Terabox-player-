"""
db.py
SQLite based simple storage - users, referral count, files used.

NOTE: Render ke free instance par disk ephemeral hota hai - agar service
restart/redeploy hoti hai to ye data reset ho sakta hai, jab tak aap
Render par persistent disk attach na karein. Chhoti scale ke liye SQLite
kaafi hai; bade scale ke liye Postgres (Render free Postgres) recommend hai.
"""

import sqlite3
import threading

DB_PATH = "bot_data.db"
_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_channel INTEGER DEFAULT 0,
                files_used INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER,
                unlocked INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def get_user(user_id: int):
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def create_user_if_not_exists(user_id: int, username: str, referred_by: int = None):
    with _lock, _conn() as conn:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by),
        )
        conn.commit()
        return True


def set_joined(user_id: int):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET joined_channel = 1 WHERE user_id = ?", (user_id,)
        )
        conn.commit()


def increment_referral(referrer_id: int):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?",
            (referrer_id,),
        )
        conn.commit()


def increment_files_used(user_id: int):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET files_used = files_used + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()


def can_use(user_id: int, free_limit: int, required_referrals: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user["files_used"] < free_limit:
        return True
    if user["referral_count"] >= required_referrals:
        return True
    return False
  
