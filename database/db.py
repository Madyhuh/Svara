import sqlite3
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).resolve().parent / "svara.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True, parents=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check and migrate languages table if needed
        cursor.execute("PRAGMA table_info(languages)")
        cols = [c["name"] for c in cursor.fetchall()]
        if "status" not in cols:
            cursor.execute("ALTER TABLE languages ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "hands_required" not in cols:
            cursor.execute("ALTER TABLE languages ADD COLUMN hands_required INTEGER NOT NULL DEFAULT 1")
        if "description" not in cols:
            cursor.execute("ALTER TABLE languages ADD COLUMN description TEXT")

        # 2. Users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Signs (Dictionary of verified & placeholder signs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language_code TEXT NOT NULL,
                label TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'alphabet',
                description TEXT,
                steps TEXT,
                is_verified INTEGER NOT NULL DEFAULT 0,
                media_url TEXT,
                FOREIGN KEY (language_code) REFERENCES languages(code) ON DELETE CASCADE,
                UNIQUE (language_code, label)
            )
        """)

        # 4. Lessons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language_code TEXT NOT NULL,
                unit_number INTEGER NOT NULL,
                order_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT,
                summary TEXT,
                target_signs TEXT,
                FOREIGN KEY (language_code) REFERENCES languages(code) ON DELETE CASCADE
            )
        """)

        # 5. Lesson Progress
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lesson_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE,
                UNIQUE (user_id, lesson_id)
            )
        """)

        # 6. Quizzes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE SET NULL
            )
        """)

        # 7. Quiz Attempts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                selected_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
            )
        """)

        # 8. Daily Learning Activity (Actual completed actions per calendar day)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                calendar_date TEXT NOT NULL, -- Format: YYYY-MM-DD
                activity_type TEXT NOT NULL, -- 'lesson_complete' | 'quiz_passed' | 'practice_sign'
                count INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (user_id, calendar_date, activity_type)
            )
        """)

        # 9. Recognition History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recognition_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                language_code TEXT NOT NULL,
                sign_label TEXT NOT NULL,
                confidence REAL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        conn.commit()

    seed_database()


def seed_database():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Languages
        languages = [
            ("ASL", "American Sign Language", "active", 1, "Supported by live student model (Letters A, B, L)."),
            ("ISL", "Indian Sign Language", "extensible", 2, "Architecture in place; awaits two-hand training data."),
            ("BSL", "British Sign Language", "extensible", 2, "Architecture in place; two-hand grammar extensible.")
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO languages (code, name, status, hands_required, description)
            VALUES (?, ?, ?, ?, ?)
        """, languages)

        # Verified Signs for ASL (A, B, L are verified with our model, others marked placeholder)
        asl_signs = [
            ("ASL", "A", "alphabet", "Fist upright, thumb resting flat against the side of the index finger.", "1. Make a relaxed fist.\n2. Keep your thumb straight beside your index finger.\n3. Face palm forward.", 1, None),
            ("ASL", "B", "alphabet", "Open palm with four fingers upright and joined; thumb folded across the palm.", "1. Hold 4 fingers straight together pointing up.\n2. Tuck your thumb flat across your palm.\n3. Face your palm forward.", 1, None),
            ("ASL", "L", "alphabet", "Hand forms an 'L' shape using the index finger upright and thumb extended sideways.", "1. Extend index finger straight up.\n2. Extend thumb at a 90-degree angle.\n3. Curl remaining 3 fingers into your palm.", 1, None),
            ("ASL", "C", "alphabet", "Curved hand forming a 'C' shape with all fingers and thumb.", "Curve fingers and thumb as if holding a small cup.", 0, None),
            ("ASL", "D", "alphabet", "Index finger points straight up while thumb touches middle, ring, and pinky tips.", "Form an upright 'd' circle with thumb and middle finger.", 0, None),
            ("ASL", "HELLO", "phrase", "Open B-hand starts near the temple and moves outward in a gentle salute.", "Salute gesture from forehead slightly outward.", 0, None),
            ("ASL", "THANK YOU", "phrase", "Fingertips touch the chin and move forward and down toward the person.", "Move flat hand from chin forward.", 0, None)
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO signs (language_code, label, category, description, steps, is_verified, media_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, asl_signs)

        # Lessons for ASL
        lessons = [
            ("ASL", 1, 1, "ASL Foundations: The Handshape A", "Discover fist alignment and thumb placement", "Master the letter A — the cornerstone of manual fingerspelling.", "A"),
            ("ASL", 1, 2, "Open Hand: Mastering B", "Straight fingers and tucking the thumb", "Learn letter B with clean finger extension and palm discipline.", "B"),
            ("ASL", 1, 3, "The Right Angle: Letter L", "Distinct thumb-index perpendicular formation", "Learn letter L, recognizable for its sharp geometry and wide usage.", "L"),
            ("ASL", 2, 1, "Contrast Practice: A, B, and L", "Transition smoothly between the three shapes", "Practice fluid motion between distinct fingerspelling states.", "A,B,L")
        ]
        for l in lessons:
            cursor.execute("""
                INSERT OR IGNORE INTO lessons (language_code, unit_number, order_index, title, subtitle, summary, target_signs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, l)

        # Quizzes
        quizzes = [
            ("Which fingers are extended when forming the ASL letter 'L'?", 
             json.dumps(["Thumb and index finger", "All four fingers", "Thumb and pinky", "Index and middle finger"]),
             "Thumb and index finger",
             "Letter L forms a 90-degree right angle with only the thumb and index finger extended."),
            ("Where should your thumb rest when signing the ASL letter 'A'?",
             json.dumps(["Flat against the side of the index finger", "Tucked underneath the palm", "Extended out at 90 degrees", "Resting between index and middle"]),
             "Flat against the side of the index finger",
             "In ASL 'A', the thumb rests upright beside the fist. Tucking it across the front turns it toward 'S' or 'E'."),
            ("In ASL letter 'B', how are the four fingers positioned?",
             json.dumps(["Held straight up and touching together", "Curled into a tight fist", "Spread apart in a fan", "Bent at the knuckles"]),
             "Held straight up and touching together",
             "ASL 'B' requires all four fingers to stand straight and joined together, with the thumb folded across the palm."),
            ("True or False: Svara's current recognition model actively supports British Sign Language (BSL).",
             json.dumps(["False — BSL is extensible and pending 2-hand training data", "True — All 3 languages are currently classified"]),
             "False — BSL is extensible and pending 2-hand training data",
             "Svara's active classifier currently runs the student-trained ASL static model (A, B, L). ISL and BSL are extensible.")
        ]
        for q in quizzes:
            cursor.execute("""
                INSERT OR IGNORE INTO quizzes (question, options_json, correct_answer, explanation)
                VALUES (?, ?, ?, ?)
            """, q)

        conn.commit()


# --- User Authentication Helpers ---

def register_user(username: str, email: str, password: str):
    username = username.strip()
    email = email.strip().lower()
    if not username or not email or not password:
        return {"success": False, "error": "All fields are required."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    password_hash = generate_password_hash(password)
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return {"success": True, "user_id": user_id, "username": username}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Username or email is already in use."}


def authenticate_user(username_or_email: str, password: str):
    term = username_or_email.strip().lower()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, password_hash FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
            (term, term)
        )
        user = cursor.fetchone()
        if user and check_password_hash(user["password_hash"], password):
            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"]
                }
            }
        return {"success": False, "error": "Invalid credentials."}


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()


# --- Activity & Streak Engine ---

def record_activity(user_id: int, activity_type: str, calendar_date: str = None):
    """
    Records completed activity for a specific calendar date (defaults to UTC today YYYY-MM-DD).
    Streaks depend strictly on completed actions (lessons, passed quizzes, verified practice).
    """
    if not calendar_date:
        calendar_date = datetime.date.today().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_activity (user_id, calendar_date, activity_type, count, updated_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, calendar_date, activity_type) DO UPDATE SET
                count = count + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, calendar_date, activity_type))
        conn.commit()


def calculate_streak(user_id: int) -> Dict[str, Any]:
    """
    Calculates consecutive active days leading up to today (or yesterday).
    Never awards a streak merely for visiting the dashboard.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT calendar_date
            FROM daily_activity
            WHERE user_id = ?
            ORDER BY calendar_date DESC
        """, (user_id,))
        rows = cursor.fetchall()

    if not rows:
        return {"current_streak": 0, "active_today": False, "last_active_date": None}

    dates = [datetime.date.fromisoformat(r["calendar_date"]) for r in rows]
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    active_today = today in dates

    # If user hasn't completed activity today or yesterday, streak is broken
    if today not in dates and yesterday not in dates:
        return {"current_streak": 0, "active_today": False, "last_active_date": dates[0].isoformat()}

    streak = 0
    current_check = today if active_today else yesterday

    for d in dates:
        if d == current_check:
            streak += 1
            current_check -= datetime.timedelta(days=1)
        elif d < current_check:
            break

    return {
        "current_streak": streak,
        "active_today": active_today,
        "last_active_date": dates[0].isoformat()
    }


def record_recognition(user_id: Optional[int], language_code: str, sign_label: str, confidence: Optional[float], status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recognition_history (user_id, language_code, sign_label, confidence, status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, language_code, sign_label, confidence, status))
        conn.commit()
