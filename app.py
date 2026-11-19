import os
import json
import sqlite3
import datetime
from pathlib import Path
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session, redirect, url_for, flash
)
from database.db import (
    init_db, get_connection, register_user, authenticate_user,
    get_user_by_id, record_activity, calculate_streak, record_recognition
)
from recognition.adapter import adapter

app = Flask(__name__)
app.secret_key = os.environ.get("SVARA_SECRET_KEY", "svara_bsc_it_project_2026_signature_key")

# Ensure DB initialized on module load
init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this section.", "notice")
            return redirect(url_for("auth_view", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_globals():
    user = None
    streak_info = {"current_streak": 0, "active_today": False}
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
        streak_info = calculate_streak(session["user_id"])
    return {
        "current_user": user,
        "user_streak": streak_info,
        "supported_languages": adapter.get_supported_languages()
    }


# ==========================================
# PAGE ROUTES
# ==========================================

@app.get("/")
def home():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_lessons FROM lessons")
        total_lessons = cursor.fetchone()["total_lessons"]
        cursor.execute("SELECT COUNT(*) AS total_signs FROM signs WHERE is_verified = 1")
        total_verified_signs = cursor.fetchone()["total_signs"]
    return render_template(
        "home.html",
        page="home",
        total_lessons=total_lessons,
        total_verified_signs=total_verified_signs
    )


@app.get("/recognize")
def recognize():
    return render_template(
        "recognize.html",
        page="recognize",
        languages=adapter.get_supported_languages()
    )


@app.get("/translate")
def translate():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, name, status, description FROM languages ORDER BY id ASC
        """)
        languages = [dict(r) for r in cursor.fetchall()]
        cursor.execute("""
            SELECT language_code, label, category, description, steps, is_verified 
            FROM signs 
            ORDER BY is_verified DESC, label ASC
        """)
        signs = [dict(r) for r in cursor.fetchall()]
    return render_template(
        "translate.html",
        page="translate",
        languages=languages,
        signs=signs
    )


@app.get("/learn")
def learn():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, unit_number, order_index, title, subtitle, summary, target_signs 
            FROM lessons 
            WHERE language_code = 'ASL' 
            ORDER BY unit_number ASC, order_index ASC
        """)
        lessons = [dict(r) for r in cursor.fetchall()]

        completed_ids = set()
        if "user_id" in session:
            cursor.execute("""
                SELECT lesson_id FROM lesson_progress WHERE user_id = ?
            """, (session["user_id"],))
            completed_ids = {r["lesson_id"] for r in cursor.fetchall()}

        for l in lessons:
            l["is_completed"] = l["id"] in completed_ids

    return render_template("learn.html", page="learn", lessons=lessons)


@app.get("/practice")
def practice():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT label, description, steps, is_verified 
            FROM signs 
            WHERE language_code = 'ASL' AND is_verified = 1
            ORDER BY label ASC
        """)
        active_signs = [dict(r) for r in cursor.fetchall()]
    return render_template("practice.html", page="practice", active_signs=active_signs)


@app.get("/quizzes")
def quizzes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.id, q.question, q.options_json, q.correct_answer, q.explanation,
                   qa.selected_answer, qa.is_correct
            FROM quizzes q
            LEFT JOIN quiz_attempts qa ON q.id = qa.quiz_id AND qa.user_id = ?
            ORDER BY q.id ASC
        """, (session.get("user_id", -1),))
        rows = cursor.fetchall()
        quiz_list = []
        for r in rows:
            quiz_list.append({
                "id": r["id"],
                "question": r["question"],
                "options": json.loads(r["options_json"]),
                "explanation": r["explanation"],
                "previous_attempt": {
                    "selected": r["selected_answer"],
                    "is_correct": bool(r["is_correct"])
                } if r["selected_answer"] is not None else None
            })
    return render_template("quizzes.html", page="quizzes", quizzes=quiz_list)


@app.get("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    with get_connection() as conn:
        cursor = conn.cursor()
        # Activity history
        cursor.execute("""
            SELECT calendar_date, activity_type, count 
            FROM daily_activity 
            WHERE user_id = ? 
            ORDER BY calendar_date DESC LIMIT 14
        """, (user_id,))
        recent_activities = [dict(r) for r in cursor.fetchall()]

        # Completed lessons
        cursor.execute("""
            SELECT l.title, l.unit_number, lp.completed_at
            FROM lesson_progress lp
            JOIN lessons l ON lp.lesson_id = l.id
            WHERE lp.user_id = ?
            ORDER BY lp.completed_at DESC
        """, (user_id,))
        completed_lessons = [dict(r) for r in cursor.fetchall()]

        # Quiz attempts
        cursor.execute("""
            SELECT q.question, qa.is_correct, qa.created_at
            FROM quiz_attempts qa
            JOIN quizzes q ON qa.quiz_id = q.id
            WHERE qa.user_id = ?
            ORDER BY qa.created_at DESC LIMIT 5
        """, (user_id,))
        recent_quizzes = [dict(r) for r in cursor.fetchall()]

        # Recognition history
        cursor.execute("""
            SELECT language_code, sign_label, confidence, status, created_at
            FROM recognition_history
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 10
        """, (user_id,))
        recent_predictions = [dict(r) for r in cursor.fetchall()]

    streak = calculate_streak(user_id)
    return render_template(
        "dashboard.html",
        page="dashboard",
        streak=streak,
        recent_activities=recent_activities,
        completed_lessons=completed_lessons,
        recent_quizzes=recent_quizzes,
        recent_predictions=recent_predictions
    )


@app.route("/auth", methods=["GET", "POST"])
def auth_view():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    mode = request.args.get("mode", "login")
    if request.method == "POST":
        action = request.form.get("action", "login")
        if action == "signup":
            username = request.form.get("username", "")
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            result = register_user(username, email, password)
            if result["success"]:
                session["user_id"] = result["user_id"]
                session["username"] = result["username"]
                flash("Welcome to Svara! Your account has been created.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash(result["error"], "error")
                mode = "signup"
        else:
            username_or_email = request.form.get("identifier", "")
            password = request.form.get("password", "")
            result = authenticate_user(username_or_email, password)
            if result["success"]:
                session["user_id"] = result["user"]["id"]
                session["username"] = result["user"]["username"]
                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)
            else:
                flash(result["error"], "error")
                mode = "login"

    return render_template("auth.html", page="auth", mode=mode)


@app.get("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "notice")
    return redirect(url_for("home"))


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.post("/api/recognize")
def api_recognize():
    """
    Receives JSON:
    {
       "language": "ASL",
       "hands": [ [ {x, y, z}, ... 21 points ] ]
    }
    Returns:
    {
       "language": "ASL",
       "status": "recognized" | "unrecognized" | "no_hand" | "model_unavailable",
       "prediction": "A" | null,
       "confidence": 0.94 | null,
       "hands_detected": 1
    }
    """
    data = request.get_json(silent=True) or {}
    language = data.get("language", "ASL")
    hands = data.get("hands", [])

    result = adapter.predict(language=language, hands_data=hands)

    # If sign recognized and user authenticated, log to history and award practice activity
    user_id = session.get("user_id")
    if result["status"] == "recognized" and result.get("prediction"):
        record_recognition(
            user_id=user_id,
            language_code=result["language"],
            sign_label=result["prediction"],
            confidence=result["confidence"],
            status=result["status"]
        )
        if user_id:
            record_activity(user_id, "practice_sign")

    return jsonify(result)


@app.get("/api/languages")
def api_languages():
    return jsonify(adapter.get_supported_languages())


@app.post("/api/text-to-sign")
def api_text_to_sign():
    """
    Reverse translation: maps letters/words to verified dictionary signs.
    Distinguishes verified vs unsupported signs.
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip().upper()
    language = data.get("language", "ASL").upper()

    if not text:
        return jsonify({"query": "", "sequence": []})

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT label, category, description, steps, is_verified, media_url
            FROM signs
            WHERE language_code = ?
        """, (language,))
        sign_map = {r["label"].upper(): dict(r) for r in cursor.fetchall()}

    sequence = []
    # Tokenize words or individual characters
    words = text.split()
    for word in words:
        # Check whole word match first
        if word in sign_map:
            s = sign_map[word]
            sequence.append({
                "token": word,
                "label": s["label"],
                "is_verified": bool(s["is_verified"]),
                "description": s["description"],
                "steps": s["steps"]
            })
        else:
            # Fingerspell character by character
            for ch in word:
                if ch.isalnum():
                    if ch in sign_map:
                        s = sign_map[ch]
                        sequence.append({
                            "token": ch,
                            "label": s["label"],
                            "is_verified": bool(s["is_verified"]),
                            "description": s["description"],
                            "steps": s["steps"]
                        })
                    else:
                        sequence.append({
                            "token": ch,
                            "label": ch,
                            "is_verified": False,
                            "description": f"Character '{ch}' is currently unsupported in {language}.",
                            "steps": "No verified model or manual demonstration available."
                        })

    return jsonify({
        "query": text,
        "language": language,
        "sequence": sequence,
        "disclaimer": "Manual demonstration sequence. Sign languages possess distinct grammar, morphology, and facial markers; sequenced fingerspelling does not replace natural sign language syntax."
    })


@app.post("/api/lessons/<int:lesson_id>/complete")
@login_required
def complete_lesson(lesson_id):
    user_id = session["user_id"]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO lesson_progress (user_id, lesson_id, completed_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, lesson_id))
        conn.commit()

    record_activity(user_id, "lesson_complete")
    streak = calculate_streak(user_id)
    return jsonify({"success": True, "lesson_id": lesson_id, "streak": streak})


@app.post("/api/quizzes/<int:quiz_id>/submit")
@login_required
def submit_quiz(quiz_id):
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    selected = data.get("selected_answer", "").strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT correct_answer, explanation FROM quizzes WHERE id = ?", (quiz_id,))
        quiz = cursor.fetchone()
        if not quiz:
            return jsonify({"success": False, "error": "Quiz not found"}), 404

        is_correct = (selected.lower() == quiz["correct_answer"].lower())
        cursor.execute("""
            INSERT INTO quiz_attempts (user_id, quiz_id, selected_answer, is_correct, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, quiz_id, selected, 1 if is_correct else 0))
        conn.commit()

    if is_correct:
        record_activity(user_id, "quiz_passed")

    streak = calculate_streak(user_id)
    return jsonify({
        "success": True,
        "is_correct": is_correct,
        "correct_answer": quiz["correct_answer"],
        "explanation": quiz["explanation"],
        "streak": streak
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
