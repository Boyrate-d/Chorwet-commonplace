import os
import re
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_connection, init_db


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", BASE_DIR / "uploads"))
UPLOADS_DIR.mkdir(exist_ok=True)
ALLOWED_UPLOADS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required")
app.secret_key = secret_key
app.config.update(
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=3600,
)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

init_db()


@app.before_request
def reject_cross_origin_mutations():
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        host = request.headers.get("Host")
        if origin and host:
            origin_host = origin.lower().split("//", 1)[-1].rstrip("/")
            if origin_host != host.lower():
                return jsonify({"success": False, "message": "Cross-origin request rejected"}), 403


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "Authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/dashboard")
def dashboard():
    if "user_id" not in session:
        return send_from_directory(FRONTEND_DIR, "login.html")
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)


@app.get("/api/health")
def health():
    return jsonify({"success": True, "status": "ok"})


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if len(username) < 3:
        return jsonify({"success": False, "message": "Username must be at least 3 characters"}), 400
    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 254:
        return jsonify({"success": False, "message": "A valid email address is required"}), 400
    if len(password) < 12:
        return jsonify({"success": False, "message": "Password must be at least 12 characters"}), 400

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO profiles (user_id, display_name) VALUES (?, ?)",
                (user_id, username),
            )
    except Exception as error:
        error_text = str(error)
        if "users.username" in error_text:
            return jsonify({"success": False, "message": "Username is already taken"}), 409
        if "users.email" in error_text or "idx_users_email" in error_text:
            return jsonify({"success": False, "message": "Email is already registered"}), 409
        return jsonify({"success": False, "message": "Unable to create account"}), 500

    session.clear()
    session["user_id"] = user_id
    session["username"] = username
    session["email"] = email
    session.permanent = True
    return jsonify({"success": True, "message": "Account created", "user": {"id": user_id, "username": username, "email": email}}), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get("identifier", data.get("username", ""))).strip().lower()
    password = str(data.get("password", ""))

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, username, email, password FROM users WHERE lower(username) = ? OR lower(email) = ?",
            (identifier, identifier),
        ).fetchone()

    if not user:
        return jsonify({"success": False, "message": "Invalid username or password"}), 401

    stored_password = user["password"]
    password_matches = (
        check_password_hash(stored_password, password)
        if stored_password.startswith(("scrypt:", "pbkdf2:", "argon2:"))
        else stored_password == password
    )

    if not password_matches:
        return jsonify({"success": False, "message": "Invalid username or password"}), 401

    if not stored_password.startswith(("scrypt:", "pbkdf2:", "argon2:")):
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), user["id"]),
            )

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]
    session.permanent = True
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {"id": user["id"], "username": user["username"], "email": user["email"]},
    })


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out"})


@app.get("/api/me")
@login_required
def me():
    return jsonify({
        "success": True,
        "user": {"id": session["user_id"], "username": session["username"], "email": session.get("email")},
    })


@app.get("/api/profile/<int:user_id>")
@login_required
def profile(user_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT users.id AS user_id, users.username, profiles.display_name,
                   profiles.bio, profiles.location, profiles.created_at,
                   (SELECT COUNT(*) FROM follows WHERE following_id = users.id) AS followers,
                   (SELECT COUNT(*) FROM follows WHERE follower_id = users.id) AS following
            FROM users
            JOIN profiles ON profiles.user_id = users.id
            WHERE users.id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return jsonify({"success": False, "message": "Profile not found"}), 404
    result = dict(row)
    result["is_self"] = user_id == session["user_id"]
    return jsonify({"success": True, "profile": result})


@app.put("/api/profile")
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    display_name = str(data.get("display_name", "")).strip()
    bio = str(data.get("bio", "")).strip()
    location = str(data.get("location", "")).strip()
    if not display_name:
        return jsonify({"success": False, "message": "Display name is required"}), 400
    if len(display_name) > 80 or len(bio) > 280 or len(location) > 80:
        return jsonify({"success": False, "message": "Profile details are too long"}), 400
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE profiles SET display_name = ?, bio = ?, location = ?
            WHERE user_id = ?
            """,
            (display_name, bio, location, session["user_id"]),
        )
    return jsonify({"success": True, "message": "Profile updated"})


@app.get("/api/circles")
def circles():
    return jsonify({
        "success": True,
        "circles": [
            {"id": 1, "name": "The Makers", "description": "Turn ideas into things—art, products, books, and everything between.", "members": 4380},
            {"id": 2, "name": "Curious Minds", "description": "Share generous questions and unexpected connections.", "members": 5120},
            {"id": 3, "name": "Good Work", "description": "Build a more thoughtful working life together.", "members": 2860},
        ],
    })


@app.get("/api/topics")
def topics():
    return jsonify({
        "success": True,
        "topics": ["Creative work", "Personal growth", "Better systems", "Culture & ideas"],
    })


@app.get("/api/stats")
def stats():
    with get_connection() as connection:
        member_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return jsonify({
        "success": True,
        "stats": {
            "members": 12000 + member_count,
            "ideas_shared_this_week": 1248,
        },
    })


@app.get("/api/posts")
def posts():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT posts.id, posts.content, posts.created_at, users.username
                   , posts.media_url, posts.media_type
            FROM posts
            JOIN users ON users.id = posts.user_id
            ORDER BY posts.id DESC
            LIMIT 50
            """
        ).fetchall()
    return jsonify({
        "success": True,
        "posts": [dict(row) for row in rows],
    })


@app.post("/api/posts")
@login_required
def create_post():
    content = str(request.form.get("content", "")).strip()
    media = request.files.get("media")
    if not content and not media:
        return jsonify({"success": False, "message": "Add text or a photo/video to your post"}), 400
    media_url = None
    media_type = None
    if media and media.filename:
        media_type = media.mimetype
        extension = ALLOWED_UPLOADS.get(media_type)
        if not extension:
            return jsonify({"success": False, "message": "Only images and MP4, WebM, or MOV videos are supported"}), 400
        filename = f"{uuid.uuid4().hex}{extension}"
        safe_name = secure_filename(filename)
        media.save(UPLOADS_DIR / safe_name)
        media_url = f"/uploads/{safe_name}"
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO posts (user_id, content, media_url, media_type) VALUES (?, ?, ?, ?)",
            (session["user_id"], content, media_url, media_type),
        )
    return jsonify({"success": True, "message": "Post shared", "post_id": cursor.lastrowid}), 201


@app.get("/api/friends")
@login_required
def friends():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT users.id, users.username
            FROM friendships
            JOIN users ON users.id = friendships.friend_id
            WHERE friendships.user_id = ? AND friendships.status = 'accepted'
            ORDER BY users.username
            """,
            (session["user_id"],),
        ).fetchall()
        suggestions = connection.execute(
            """
            SELECT id, username FROM users
            WHERE id != ? AND id NOT IN (
                SELECT friend_id FROM friendships WHERE user_id = ?
            )
            ORDER BY username LIMIT 20
            """,
            (session["user_id"], session["user_id"]),
        ).fetchall()
    return jsonify({
        "success": True,
        "friends": [dict(row) for row in rows],
        "suggestions": [dict(row) for row in suggestions],
    })


@app.get("/api/network")
@login_required
def network():
    with get_connection() as connection:
        following = connection.execute(
            """
            SELECT users.id, users.username FROM follows
            JOIN users ON users.id = follows.following_id
            WHERE follows.follower_id = ? ORDER BY users.username
            """,
            (session["user_id"],),
        ).fetchall()
        followers = connection.execute(
            """
            SELECT users.id, users.username FROM follows
            JOIN users ON users.id = follows.follower_id
            WHERE follows.following_id = ? ORDER BY users.username
            """,
            (session["user_id"],),
        ).fetchall()
        suggestions = connection.execute(
            """
            SELECT id, username FROM users
            WHERE id != ? AND id NOT IN (
                SELECT following_id FROM follows WHERE follower_id = ?
            )
            ORDER BY username LIMIT 20
            """,
            (session["user_id"], session["user_id"]),
        ).fetchall()
    return jsonify({
        "success": True,
        "following": [dict(row) for row in following],
        "followers": [dict(row) for row in followers],
        "suggestions": [dict(row) for row in suggestions],
    })


@app.post("/api/follow/<int:user_id>")
@login_required
def follow(user_id):
    if user_id == session["user_id"]:
        return jsonify({"success": False, "message": "You cannot follow yourself"}), 400
    with get_connection() as connection:
        user = connection.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        existing = connection.execute(
            "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
            (session["user_id"], user_id),
        ).fetchone()
        if existing:
            connection.execute(
                "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
                (session["user_id"], user_id),
            )
            following = False
        else:
            connection.execute(
                "INSERT INTO follows (follower_id, following_id) VALUES (?, ?)",
                (session["user_id"], user_id),
            )
            following = True
    return jsonify({"success": True, "following": following, "message": "Follow status updated"})


@app.post("/api/friends")
@login_required
def add_friend():
    data = request.get_json(silent=True) or {}
    friend_id = data.get("friend_id")
    if not isinstance(friend_id, int) or friend_id == session["user_id"]:
        return jsonify({"success": False, "message": "Choose a valid friend"}), 400
    with get_connection() as connection:
        user_exists = connection.execute("SELECT id FROM users WHERE id = ?", (friend_id,)).fetchone()
        if not user_exists:
            return jsonify({"success": False, "message": "User not found"}), 404
        connection.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (session["user_id"], friend_id),
        )
        connection.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (friend_id, session["user_id"]),
        )
        friend = connection.execute("SELECT username FROM users WHERE id = ?", (friend_id,)).fetchone()
        connection.execute(
            "INSERT INTO notifications (user_id, content) VALUES (?, ?)",
            (friend_id, f"{session['username']} added you as a friend"),
        )
    return jsonify({"success": True, "message": f"{friend['username']} added to friends"})


@app.get("/api/events")
@login_required
def events():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT events.id, events.title, events.description, events.location,
                   events.event_date, events.category,
                   COUNT(event_attendees.user_id) AS attendees,
                   MAX(CASE WHEN event_attendees.user_id = ? THEN 1 ELSE 0 END) AS attending
            FROM events
            LEFT JOIN event_attendees ON event_attendees.event_id = events.id
            GROUP BY events.id
            ORDER BY events.event_date
            """,
            (session["user_id"],),
        ).fetchall()
    return jsonify({"success": True, "events": [dict(row) for row in rows]})


@app.post("/api/events")
@login_required
def create_event():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    location = str(data.get("location", "")).strip()
    event_date = str(data.get("event_date", "")).strip()
    category = str(data.get("category", "Community")).strip()
    if not all([title, description, location, event_date]):
        return jsonify({"success": False, "message": "Complete all event details"}), 400
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO events (title, description, location, event_date, category, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, location, event_date, category, session["user_id"]),
        )
    return jsonify({"success": True, "message": "Event created"}), 201


@app.post("/api/events/<int:event_id>/rsvp")
@login_required
def rsvp_event(event_id):
    with get_connection() as connection:
        event = connection.execute("SELECT id, title FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return jsonify({"success": False, "message": "Event not found"}), 404
        existing = connection.execute(
            "SELECT 1 FROM event_attendees WHERE event_id = ? AND user_id = ?",
            (event_id, session["user_id"]),
        ).fetchone()
        if existing:
            connection.execute(
                "DELETE FROM event_attendees WHERE event_id = ? AND user_id = ?",
                (event_id, session["user_id"]),
            )
            attending = False
        else:
            connection.execute(
                "INSERT INTO event_attendees (event_id, user_id) VALUES (?, ?)",
                (event_id, session["user_id"]),
            )
            attending = True
    return jsonify({"success": True, "attending": attending, "message": "Event attendance updated"})


@app.get("/api/culture")
@login_required
def culture():
    return jsonify({
        "success": True,
        "stories": [
            {"title": "The language we carry", "category": "Living language", "description": "Share a word, saying, or phrase from home and the story behind it.", "color": "sage"},
            {"title": "Recipes with roots", "category": "Food & memory", "description": "Document the meals, ingredients, and family rituals that bring people together.", "color": "peach"},
            {"title": "Places that remember", "category": "Land & legacy", "description": "Explore the landmarks and landscapes that hold meaning for our community.", "color": "blue"},
            {"title": "Made by hand", "category": "Craft & art", "description": "Celebrate makers preserving skills through music, textiles, carving, and design.", "color": "coral"},
        ],
    })


@app.get("/api/notifications")
@login_required
def notifications():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, content, is_read, created_at FROM notifications
            WHERE user_id = ? ORDER BY id DESC LIMIT 50
            """,
            (session["user_id"],),
        ).fetchall()
    return jsonify({"success": True, "notifications": [dict(row) for row in rows]})


@app.get("/api/announcements")
@login_required
def announcements():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, content, category, published_at
            FROM announcements ORDER BY id DESC LIMIT 20
            """
        ).fetchall()
    return jsonify({"success": True, "announcements": [dict(row) for row in rows]})


@app.post("/api/notifications/read")
@login_required
def read_notifications():
    with get_connection() as connection:
        connection.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
            (session["user_id"],),
        )
    return jsonify({"success": True, "message": "Notifications marked as read"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
