from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for session management

# Initialize the database
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            quiz_completed INTEGER DEFAULT 0
        )
    """)
    # Create table for storing quiz answers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_responses (
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            PRIMARY KEY (user_id, question_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, quiz_completed FROM users WHERE username = ? AND password = ?", 
                       (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            user_id, username, _, quiz_completed = user
            session["user_id"] = int(user_id)  # Ensure user_id is an integer
            session["question_index"] = get_last_question_index(user_id)  # Resume progress
            if quiz_completed:
                return redirect(url_for("recommendations"))
            return redirect(url_for("questionnaire"))
        else:
            flash("Username and password don't match. Try again or create an account.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, password, email))
            conn.commit()
            conn.close()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists. Please choose a different one.", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            session["reset_user_id"] = user[0]
            flash("Email verified! Please reset your password.", "info")
            return redirect(url_for("reset_password"))
        else:
            flash("Email not found. Please check and try again.", "error")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user_id")

    if not user_id:
        flash("Unauthorized access. Please verify your email first.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return redirect(url_for("reset_password"))

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        conn.commit()
        conn.close()

        session.pop("reset_user_id", None)
        flash("Password reset successfully! You can now log in.", "success")
        return redirect(url_for("home"))

    return render_template("reset_password.html")


questions = [
    {"id": 1, "question": "What is your preferred movie duration?", 
     "options": ["Short (<90 mins)", "Medium (90-120 mins)", "Long (>120 mins)"]},
    {"id": 2, "question": "What genre do you prefer?", 
     "options": ["Action", "Romance", "Comedy", "Thriller", "Horror"]},
    {"id": 3, "question": "Which actor would you like to see?", 
     "options": ["Leonardo DiCaprio", "Scarlett Johansson", "Tom Cruise", "Meryl Streep"]},
    {"id": 4, "question": "What vibe are you looking for?", 
     "options": ["Exciting", "Romantic", "Chill", "Mysterious", "Scary"]},
]

@app.route("/questionnaire", methods=["GET", "POST"])
def questionnaire():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    question_index = session.get("question_index", 0)

    if question_index >= len(questions):
        mark_quiz_completed(user_id)
        return redirect(url_for("recommendations"))

    current_question = questions[question_index]

    if request.method == "POST":
        if "previous" in request.form:
            session["question_index"] = max(0, question_index - 1)
        else:
            answer = request.form.get("answer")
            save_answer(user_id, current_question["id"], answer)
            session["question_index"] += 1
        return redirect(url_for("questionnaire"))

    return render_template("questionnaire.html", question=current_question, question_index=question_index)


@app.route("/recommendations")
def recommendations():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    answers = get_answers(user_id)
    recommendations = [
        {"title": "Inception", "reason": "You like exciting, mysterious movies."},
        {"title": "Titanic", "reason": "You enjoy romantic, long movies."},
        {"title": "The Dark Knight", "reason": "You prefer thrilling action movies."},
    ]
    return render_template("recommendations.html", recommendations=recommendations, answers=answers)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# Helper functions
def save_answer(user_id, question_id, answer):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO quiz_responses (user_id, question_id, answer) VALUES (?, ?, ?)
    """, (user_id, question_id, answer))
    conn.commit()
    conn.close()


def get_last_question_index(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(question_id) FROM quiz_responses WHERE user_id = ?
    """, (user_id,))
    last_question_id = cursor.fetchone()[0]
    conn.close()
    return last_question_id if last_question_id else 0


def mark_quiz_completed(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET quiz_completed = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_answers(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT question_id, answer FROM quiz_responses WHERE user_id = ?", (user_id,))
    answers = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return answers


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)