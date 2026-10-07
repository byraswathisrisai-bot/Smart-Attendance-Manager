from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
from math import ceil


# ==========================================================
# FLASK APP
# ==========================================================

app = Flask(__name__)

app.secret_key = "smart-attendance-demo-key"

DB = Path(__file__).with_name("attendance.db")


# ==========================================================
# DATABASE
# ==========================================================

def get_db():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ==========================================================
# INITIALIZE DATABASE
# ==========================================================

def init_db():

    conn = get_db()

    conn.executescript("""

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            role TEXT NOT NULL DEFAULT 'student'

        );


        CREATE TABLE IF NOT EXISTS subjects (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            code TEXT NOT NULL,

            total_classes INTEGER NOT NULL DEFAULT 0,

            attended_classes INTEGER NOT NULL DEFAULT 0

        );


        CREATE TABLE IF NOT EXISTS class_sessions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            subject_id INTEGER NOT NULL,

            class_number INTEGER NOT NULL,

            FOREIGN KEY (subject_id)
                REFERENCES subjects(id)

        );


        CREATE TABLE IF NOT EXISTS attendance_records (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            class_id INTEGER NOT NULL,

            student_id INTEGER NOT NULL,

            status TEXT NOT NULL,

            UNIQUE(class_id, student_id),

            FOREIGN KEY (class_id)
                REFERENCES class_sessions(id),

            FOREIGN KEY (student_id)
                REFERENCES users(id)

        );

    """)


    # ======================================================
    # DEMO STUDENT
    # ======================================================

    conn.execute("""
        INSERT OR IGNORE INTO users
        (id, name, email, password, role)

        VALUES
        (
            1,
            'Demo Student',
            'student@college.com',
            'student123',
            'student'
        )
    """)


    # ======================================================
    # DEMO ADMIN
    # ======================================================

    conn.execute("""
        INSERT OR IGNORE INTO users
        (id, name, email, password, role)

        VALUES
        (
            2,
            'Faculty Admin',
            'admin@college.com',
            'admin123',
            'admin'
        )
    """)


    # ======================================================
    # DEFAULT SUBJECTS
    # ONLY CREATED IF DATABASE HAS NO SUBJECTS
    # ======================================================

    subject_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM subjects
        """
    ).fetchone()["count"]


    if subject_count == 0:

        conn.execute("""
            INSERT INTO subjects
            (name, code, total_classes, attended_classes)

            VALUES
            (
                'Python Programming',
                'CS101',
                0,
                0
            )
        """)


        conn.execute("""
            INSERT INTO subjects
            (name, code, total_classes, attended_classes)

            VALUES
            (
                'Database Management',
                'CS102',
                0,
                0
            )
        """)


        conn.execute("""
            INSERT INTO subjects
            (name, code, total_classes, attended_classes)

            VALUES
            (
                'Computer Networks',
                'CS103',
                0,
                0
            )
        """)


    conn.commit()

    create_missing_class_sessions(conn)

    conn.commit()

    conn.close()


# ==========================================================
# CREATE MISSING CLASS SESSIONS
# ==========================================================

def create_missing_class_sessions(conn):

    subjects = conn.execute(
        """
        SELECT *
        FROM subjects
        ORDER BY id
        """
    ).fetchall()


    for subject in subjects:

        existing_count = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM class_sessions

            WHERE subject_id=?
            """,
            (subject["id"],)
        ).fetchone()["count"]


        total = subject["total_classes"]


        if existing_count < total:

            for number in range(
                existing_count + 1,
                total + 1
            ):

                conn.execute(
                    """
                    INSERT INTO class_sessions
                    (
                        subject_id,
                        class_number
                    )

                    VALUES (?, ?)
                    """,
                    (
                        subject["id"],
                        number
                    )
                )


# ==========================================================
# PERCENTAGE
# ==========================================================

def percentage(attended, total):

    if total == 0:
        return 0

    return round(
        attended * 100 / total,
        2
    )


# ==========================================================
# ATTENDANCE STATUS
# ==========================================================

def attendance_status(percent):

    if percent >= 75:
        return "Safe"

    elif percent >= 65:
        return "Warning"

    else:
        return "Critical"


# ==========================================================
# CAN MISS
# ==========================================================

def can_miss(attended, total, required=75):

    if total == 0:
        return 0

    if required >= 100:
        return 0

    return max(
        0,
        (attended * 100 - required * total)
        // required
    )


# ==========================================================
# NEED TO REACH
# ==========================================================

def need_to_reach(attended, total, required=75):

    if total == 0:
        return 0

    current = percentage(
        attended,
        total
    )

    if current >= required:
        return 0

    return ceil(
        (
            required * total
            - 100 * attended
        )
        /
        (100 - required)
    )


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"].strip()

        password = request.form["password"]


        conn = get_db()


        user = conn.execute(
            """
            SELECT *

            FROM users

            WHERE email=?
            AND password=?
            """,
            (
                email,
                password
            )
        ).fetchone()


        conn.close()


        if user:

            session["user_id"] = user["id"]

            session["name"] = user["name"]

            session["role"] = user["role"]


            if user["role"] == "admin":

                return redirect(
                    url_for("admin")
                )


            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ==========================================================
# STUDENT DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if session.get("role") == "admin":

        return redirect(
            url_for("admin")
        )


    student_id = session["user_id"]

    conn = get_db()


    subjects = conn.execute(
        """
        SELECT *

        FROM subjects

        ORDER BY id
        """
    ).fetchall()


    subject_data = []

    overall_attended = 0

    overall_total = 0


    for subject in subjects:


        # PRESENT

        attended = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM attendance_records ar

            JOIN class_sessions cs

            ON ar.class_id = cs.id

            WHERE cs.subject_id=?

            AND ar.student_id=?

            AND ar.status='present'
            """,
            (
                subject["id"],
                student_id
            )
        ).fetchone()["count"]


        # ABSENT

        absent = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM attendance_records ar

            JOIN class_sessions cs

            ON ar.class_id = cs.id

            WHERE cs.subject_id=?

            AND ar.student_id=?

            AND ar.status='absent'
            """,
            (
                subject["id"],
                student_id
            )
        ).fetchone()["count"]


        total = subject["total_classes"]


        percent = percentage(
            attended,
            total
        )


        overall_attended += attended

        overall_total += total


        subject_data.append({

            "id": subject["id"],

            "name": subject["name"],

            "code": subject["code"],

            "attended": attended,

            "absent": absent,

            "total": total,

            "percentage": percent,

            "status": attendance_status(
                percent
            )

        })


    overall = percentage(
        overall_attended,
        overall_total
    )


    conn.close()


    return render_template(

        "dashboard.html",

        subjects=subject_data,

        overall=overall,

        status=attendance_status(
            overall
        ),

        can_miss=can_miss(
            overall_attended,
            overall_total
        ),

        need=need_to_reach(
            overall_attended,
            overall_total
        )

    )


# ==========================================================
# ADMIN AJAX RESPONSE HELPER
# ==========================================================

def admin_action_response(message, category="success"):

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return jsonify({
            "success": category not in ["danger"],
            "message": message,
            "category": category
        })

    flash(message, category)

    return redirect(url_for("admin"))


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin")
def admin():

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )


    conn = get_db()


    # USERS

    users = conn.execute(
        """
        SELECT *

        FROM users

        ORDER BY id
        """
    ).fetchall()


    # SUBJECTS

    subjects = conn.execute(
        """
        SELECT *

        FROM subjects

        ORDER BY id
        """
    ).fetchall()


    # ======================================================
    # ONLY NEXT UNMARKED CLASS FOR EACH SUBJECT
    # ======================================================

    classes = conn.execute(
        """
        SELECT
            cs.id,
            cs.subject_id,
            cs.class_number,
            s.name,
            s.code

        FROM class_sessions cs

        JOIN subjects s
        ON cs.subject_id = s.id

        LEFT JOIN attendance_records ar

        ON cs.id = ar.class_id

        AND ar.student_id = 1

        WHERE ar.id IS NULL

        AND cs.class_number = (

            SELECT MIN(cs2.class_number)

            FROM class_sessions cs2

            LEFT JOIN attendance_records ar2

            ON cs2.id = ar2.class_id

            AND ar2.student_id = 1

            WHERE cs2.subject_id = cs.subject_id

            AND ar2.id IS NULL

        )

        ORDER BY cs.subject_id
        """
    ).fetchall()


    conn.close()


    return render_template(

        "admin.html",

        users=users,

        subjects=subjects,

        classes=classes

    )


# ==========================================================
# ADMIN DATA FOR AJAX REFRESH
# ==========================================================

@app.route("/admin/data")
def admin_data():

    if session.get("role") != "admin":

        return jsonify({
            "success": False,
            "message": "Admin access required."
        }), 403

    conn = get_db()

    subjects = conn.execute(
        """
        SELECT id, name, code, total_classes
        FROM subjects
        ORDER BY id
        """
    ).fetchall()

    classes = conn.execute(
        """
        SELECT
            cs.id,
            cs.subject_id,
            cs.class_number,
            s.name,
            s.code

        FROM class_sessions cs

        JOIN subjects s
        ON cs.subject_id = s.id

        LEFT JOIN attendance_records ar
        ON cs.id = ar.class_id
        AND ar.student_id = 1

        WHERE ar.id IS NULL

        AND cs.class_number = (

            SELECT MIN(cs2.class_number)

            FROM class_sessions cs2

            LEFT JOIN attendance_records ar2
            ON cs2.id = ar2.class_id
            AND ar2.student_id = 1

            WHERE cs2.subject_id = cs.subject_id
            AND ar2.id IS NULL
        )

        ORDER BY cs.subject_id
        """
    ).fetchall()

    users_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    conn.close()

    return jsonify({
        "success": True,
        "users_count": users_count,
        "subjects": [dict(row) for row in subjects],
        "classes": [dict(row) for row in classes]
    })


# ==========================================================
# CONDUCT ONE CLASS
# ==========================================================

@app.route(
    "/admin/conduct_class/<int:subject_id>",
    methods=["POST"]
)
def conduct_class(subject_id):

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )

    conn = get_db()

    subject = conn.execute(
        """
        SELECT *
        FROM subjects
        WHERE id=?
        """,
        (subject_id,)
    ).fetchone()

    if not subject:

        conn.close()

        return admin_action_response(
            "Subject not found.",
            "danger"
        )

    new_class_number = subject["total_classes"] + 1

    conn.execute(
        """
        INSERT INTO class_sessions
        (
            subject_id,
            class_number
        )
        VALUES (?, ?)
        """,
        (
            subject_id,
            new_class_number
        )
    )

    conn.execute(
        """
        UPDATE subjects
        SET total_classes = total_classes + 1
        WHERE id=?
        """,
        (subject_id,)
    )

    conn.commit()
    conn.close()

    return admin_action_response(
        f"Class {new_class_number} conducted for {subject['name']}.",
        "success"
    )


# ==========================================================
# MODIFY TOTAL CLASSES
# ==========================================================

@app.route(
    "/admin/modify_classes/<int:subject_id>",
    methods=["POST"]
)
def modify_classes(subject_id):

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )

    try:

        new_total = int(
            request.form["total_classes"]
        )

    except (
        ValueError,
        TypeError,
        KeyError
    ):

        return admin_action_response(
            "Please enter a valid number.",
            "danger"
        )

    if new_total < 0:

        return admin_action_response(
            "Number of classes cannot be negative.",
            "danger"
        )

    conn = get_db()

    subject = conn.execute(
        """
        SELECT *
        FROM subjects
        WHERE id=?
        """,
        (subject_id,)
    ).fetchone()

    if not subject:

        conn.close()

        return admin_action_response(
            "Subject not found.",
            "danger"
        )

    old_total = subject["total_classes"]

    # Increase classes
    if new_total > old_total:

        for class_number in range(
            old_total + 1,
            new_total + 1
        ):

            conn.execute(
                """
                INSERT INTO class_sessions
                (
                    subject_id,
                    class_number
                )
                VALUES (?, ?)
                """,
                (
                    subject_id,
                    class_number
                )
            )

    # Decrease classes
    elif new_total < old_total:

        marked_count = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM attendance_records ar

            JOIN class_sessions cs
            ON ar.class_id = cs.id

            WHERE cs.subject_id=?
            AND cs.class_number>?
            """,
            (
                subject_id,
                new_total
            )
        ).fetchone()["count"]

        if marked_count > 0:

            conn.close()

            return admin_action_response(
                "Cannot reduce classes because attendance is already marked for some of those classes.",
                "danger"
            )

        conn.execute(
            """
            DELETE FROM attendance_records

            WHERE class_id IN (

                SELECT id
                FROM class_sessions
                WHERE subject_id=?
                AND class_number>?
            )
            """,
            (
                subject_id,
                new_total
            )
        )

        conn.execute(
            """
            DELETE FROM class_sessions

            WHERE subject_id=?
            AND class_number>?
            """,
            (
                subject_id,
                new_total
            )
        )

    conn.execute(
        """
        UPDATE subjects
        SET total_classes=?
        WHERE id=?
        """,
        (
            new_total,
            subject_id
        )
    )

    conn.commit()
    conn.close()

    return admin_action_response(
        f"Total classes for {subject['name']} updated to {new_total}.",
        "success"
    )


# ==========================================================
# MARK PRESENT / ABSENT
# ==========================================================

@app.route(
    "/admin/attendance/<int:class_id>/<status_value>",
    methods=["POST"]
)
def admin_mark_attendance(
    class_id,
    status_value
):

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )

    if status_value not in [
        "present",
        "absent"
    ]:

        return admin_action_response(
            "Invalid attendance status.",
            "danger"
        )

    # Demo student
    student_id = 1

    conn = get_db()

    class_session = conn.execute(
        """
        SELECT
            cs.*,
            s.name AS subject_name

        FROM class_sessions cs

        JOIN subjects s
        ON cs.subject_id = s.id

        WHERE cs.id=?
        """,
        (class_id,)
    ).fetchone()

    if not class_session:

        conn.close()

        return admin_action_response(
            "Class not found.",
            "danger"
        )

    existing = conn.execute(
        """
        SELECT *
        FROM attendance_records
        WHERE class_id=?
        AND student_id=?
        """,
        (
            class_id,
            student_id
        )
    ).fetchone()

    if existing:

        conn.close()

        return admin_action_response(
            "Attendance is already marked.",
            "warning"
        )

    conn.execute(
        """
        INSERT INTO attendance_records
        (
            class_id,
            student_id,
            status
        )
        VALUES (?, ?, ?)
        """,
        (
            class_id,
            student_id,
            status_value
        )
    )

    conn.commit()
    conn.close()

    if status_value == "present":

        message = (
            f"Student marked Present for "
            f"{class_session['subject_name']} "
            f"Class {class_session['class_number']}."
        )

    else:

        message = (
            f"Student marked Absent for "
            f"{class_session['subject_name']} "
            f"Class {class_session['class_number']}."
        )

    return admin_action_response(
        message,
        "success" if status_value == "present" else "warning"
    )


# ==========================================================
# SUBJECTS
# ==========================================================

@app.route(
    "/subjects",
    methods=["GET", "POST"]
)
def subjects():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    conn = get_db()


    if request.method == "POST":

        if session.get("role") != "admin":

            conn.close()

            flash(
                "Only admin can add subjects.",
                "danger"
            )

            return redirect(
                url_for("subjects")
            )


        name = request.form["name"].strip()

        code = request.form["code"].strip()


        if name and code:

            conn.execute(
                """
                INSERT INTO subjects
                (
                    name,
                    code,
                    total_classes,
                    attended_classes
                )

                VALUES (?, ?, 0, 0)
                """,
                (
                    name,
                    code
                )
            )


            conn.commit()


            flash(
                "Subject added successfully.",
                "success"
            )


    rows = conn.execute(
        """
        SELECT *

        FROM subjects

        ORDER BY id
        """
    ).fetchall()


    conn.close()


    return render_template(
        "subjects.html",
        subjects=rows
    )


# ==========================================================
# DELETE SUBJECT
# ==========================================================

@app.route(
    "/delete_subject/<int:subject_id>",
    methods=["POST"]
)
def delete_subject(subject_id):

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )


    conn = get_db()


    conn.execute(
        """
        DELETE FROM attendance_records

        WHERE class_id IN (

            SELECT id

            FROM class_sessions

            WHERE subject_id=?

        )
        """,
        (subject_id,)
    )


    conn.execute(
        """
        DELETE FROM class_sessions

        WHERE subject_id=?
        """,
        (subject_id,)
    )


    conn.execute(
        """
        DELETE FROM subjects

        WHERE id=?
        """,
        (subject_id,)
    )


    conn.commit()

    conn.close()


    flash(
        "Subject deleted successfully.",
        "success"
    )


    return redirect(
        url_for("subjects")
    )


# ==========================================================
# PREDICTION
# ==========================================================

@app.route("/prediction")
def prediction():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    student_id = session["user_id"]


    conn = get_db()


    subjects = conn.execute(
        """
        SELECT *

        FROM subjects

        ORDER BY id
        """
    ).fetchall()


    data = []


    for subject in subjects:


        attended = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM attendance_records ar

            JOIN class_sessions cs

            ON ar.class_id = cs.id

            WHERE cs.subject_id=?

            AND ar.student_id=?

            AND ar.status='present'
            """,
            (
                subject["id"],
                student_id
            )
        ).fetchone()["count"]


        absent = conn.execute(
            """
            SELECT COUNT(*) AS count

            FROM attendance_records ar

            JOIN class_sessions cs

            ON ar.class_id = cs.id

            WHERE cs.subject_id=?

            AND ar.student_id=?

            AND ar.status='absent'
            """,
            (
                subject["id"],
                student_id
            )
        ).fetchone()["count"]


        total = subject["total_classes"]


        percent = percentage(
            attended,
            total
        )


        data.append({

            "name": subject["name"],

            "code": subject["code"],

            "attended": attended,

            "absent": absent,

            "total": total,

            "percentage": percent,

            "status": attendance_status(
                percent
            ),

            "can_miss": can_miss(
                attended,
                total
            ),

            "need": need_to_reach(
                attended,
                total
            )

        })


    conn.close()


    return render_template(
        "prediction.html",
        data=data
    )


# ==========================================================
# START DATABASE
# ==========================================================

init_db()


# ==========================================================
# RUN APP
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )