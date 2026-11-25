import os
import sqlite3
from pathlib import Path


DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).resolve().parent / "users.db"))


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password TEXT NOT NULL
            )
            """
        )
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                bio TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO profiles (user_id, display_name)
            SELECT id, username FROM users
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                media_url TEXT,
                media_type TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        post_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(posts)").fetchall()
        }
        if "media_url" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN media_url TEXT")
        if "media_type" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN media_type TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'accepted',
                UNIQUE(user_id, friend_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id),
                FOREIGN KEY (recipient_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                event_date TEXT NOT NULL,
                category TEXT NOT NULL,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_attendees (
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                UNIQUE(event_id, user_id),
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS follows (
                follower_id INTEGER NOT NULL,
                following_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(follower_id, following_id),
                FOREIGN KEY (follower_id) REFERENCES users(id),
                FOREIGN KEY (following_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO events
                (id, title, description, location, event_date, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Chorwet Story Circle", "An evening of local stories, memories, and the people who keep them alive.", "Chorwet Community Hall", "2026-12-05 15:00", "Heritage"),
                (2, "Ideas Under the Acacia", "Bring one idea and leave with new connections at our open community gathering.", "Chepkiit Gardens", "2026-12-12 10:00", "Community"),
                (3, "Young Creators Workshop", "A friendly hands-on afternoon for artists, makers, and curious young minds.", "Common Place Studio", "2026-12-19 13:00", "Creative"),
            ],
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO announcements (id, title, content, category)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "Welcome to Chorwet Common Place", "This is a shared space for ideas, culture, and the people who make our community special.", "From the team"),
                (2, "Tell us what should happen next", "Follow people you admire, join an event, and share one thing you would love to see in Chorwet.", "Community note"),
            ],
        )
