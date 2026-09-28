from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

app.secret_key = "crime_reporting_system_secret_key"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    conn = sqlite3.connect("database.db")

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_database():

    conn = get_db_connection()

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            role TEXT NOT NULL

        )
    """)


    # COMPLAINTS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE NOT NULL,

            citizen_id INTEGER NOT NULL,

            crime_type TEXT NOT NULL,

            incident_date TEXT NOT NULL,

            location TEXT NOT NULL,

            description TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'Submitted',

            created_at TEXT NOT NULL,

            FOREIGN KEY (citizen_id)
            REFERENCES users(id)

        )
    """)


    # NOTIFICATIONS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            message TEXT NOT NULL,

            is_read INTEGER DEFAULT 0,

            created_at TEXT NOT NULL,

            FOREIGN KEY (user_id)
            REFERENCES users(id)

        )
    """)


    conn.commit()

    conn.close()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    return render_template("index.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]

        email = request.form["email"]

        password = request.form["password"]

        role = request.form["role"]


        hashed_password = generate_password_hash(password)


        conn = get_db_connection()


        try:

            conn.execute("""
                INSERT INTO users
                (name, email, password, role)

                VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password,
                role
            ))


            conn.commit()

            conn.close()


            return redirect(url_for("login"))


        except sqlite3.IntegrityError:

            conn.close()


            return render_template(
                "register.html",
                error="This email is already registered."
            )


    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]


        conn = get_db_connection()


        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """,
        (email,)).fetchone()


        conn.close()


        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["name"] = user["name"]

            session["role"] = user["role"]


            # CITIZEN
            if user["role"] == "Citizen":

                return redirect(
                    url_for("citizen_dashboard")
                )


            # POLICE
            elif user["role"] == "Police":

                return redirect(
                    url_for("police_dashboard")
                )


            # ADMIN
            elif user["role"] == "Admin":

                return redirect(
                    url_for("admin_dashboard")
                )


        return render_template(
            "login.html",
            error="Invalid email or password."
        )


    return render_template("login.html")


# ============================================================
# CITIZEN DASHBOARD
# ============================================================

@app.route("/citizen_dashboard")
def citizen_dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Citizen":

        return "Access Denied"


    return render_template(
        "citizen_dashboard.html",
        name=session["name"]
    )


# ============================================================
# REPORT CRIME
# ============================================================

@app.route("/report_crime", methods=["GET", "POST"])
def report_crime():

    # Check login
    if "user_id" not in session:

        return redirect(url_for("login"))


    # Check citizen
    if session["role"] != "Citizen":

        return "Access Denied"


    if request.method == "POST":

        crime_type = request.form["crime_type"]

        incident_date = request.form["incident_date"]

        location = request.form["location"]

        description = request.form["description"]


        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        conn = get_db_connection()


        # Temporary complaint ID
        temporary_id = "TEMP"


        cursor = conn.execute("""
            INSERT INTO complaints
            (
                complaint_id,
                citizen_id,
                crime_type,
                incident_date,
                location,
                description,
                status,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            temporary_id,
            session["user_id"],
            crime_type,
            incident_date,
            location,
            description,
            "Submitted",
            created_at
        ))


        complaint_database_id = cursor.lastrowid


        # Generate complaint ID
        complaint_id = "CR" + str(
            complaint_database_id
        ).zfill(4)


        # Update complaint ID
        conn.execute("""
            UPDATE complaints

            SET complaint_id = ?

            WHERE id = ?
        """,
        (
            complaint_id,
            complaint_database_id
        ))


        # Create notification
        message = (
            "Your complaint "
            + complaint_id
            + " has been submitted successfully."
        )


        conn.execute("""
            INSERT INTO notifications
            (
                user_id,
                message,
                created_at
            )

            VALUES (?, ?, ?)
        """,
        (
            session["user_id"],
            message,
            created_at
        ))


        conn.commit()

        conn.close()


        return render_template(
            "report_crime.html",
            success=(
                "Complaint submitted successfully! "
                "Your Complaint ID is "
                + complaint_id
            )
        )


    return render_template("report_crime.html")


# ============================================================
# MY COMPLAINTS
# ============================================================

@app.route("/my_complaints")
def my_complaints():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Citizen":

        return "Access Denied"


    conn = get_db_connection()


    complaints = conn.execute("""
        SELECT *

        FROM complaints

        WHERE citizen_id = ?

        ORDER BY id DESC
    """,
    (
        session["user_id"],
    )).fetchall()


    conn.close()


    return render_template(
        "my_complaints.html",
        complaints=complaints
    )


# ============================================================
# TRACK COMPLAINT
# ============================================================

@app.route("/track_complaint", methods=["GET", "POST"])
def track_complaint():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Citizen":

        return "Access Denied"


    complaint = None

    error = None


    if request.method == "POST":

        complaint_id = request.form[
            "complaint_id"
        ].strip()


        conn = get_db_connection()


        complaint = conn.execute("""
            SELECT *

            FROM complaints

            WHERE complaint_id = ?

            AND citizen_id = ?
        """,
        (
            complaint_id,
            session["user_id"]
        )).fetchone()


        conn.close()


        if complaint is None:

            error = (
                "Complaint not found. "
                "Please check your Complaint ID."
            )


    return render_template(
        "track_complaint.html",
        complaint=complaint,
        error=error
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
def notifications():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Citizen":

        return "Access Denied"


    conn = get_db_connection()


    notifications = conn.execute("""
        SELECT *

        FROM notifications

        WHERE user_id = ?

        ORDER BY id DESC
    """,
    (
        session["user_id"],
    )).fetchall()


    # Mark notifications as read
    conn.execute("""
        UPDATE notifications

        SET is_read = 1

        WHERE user_id = ?
    """,
    (
        session["user_id"],
    ))


    conn.commit()

    conn.close()


    return render_template(
        "notifications.html",
        notifications=notifications
    )

# ============================================================
# POLICE - VIEW COMPLAINTS
# ============================================================

@app.route("/police_complaints")
def police_complaints():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
        return "Access Denied"

    conn = get_db_connection()

    complaints = conn.execute("""
        SELECT
            complaints.*,
            users.name AS citizen_name
        FROM complaints
        JOIN users
        ON complaints.citizen_id = users.id
        ORDER BY complaints.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "police_complaints.html",
        complaints=complaints
    )


# ============================================================
# POLICE - UPDATE COMPLAINT
# ============================================================

@app.route(
    "/update_complaint/<complaint_id>",
    methods=["GET", "POST"]
)
def update_complaint(complaint_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
        return "Access Denied"

    conn = get_db_connection()

    complaint = conn.execute("""
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
    """, (complaint_id,)).fetchone()

    if complaint is None:
        conn.close()
        return "Complaint not found"

    if request.method == "POST":

        new_status = request.form["status"]

        conn.execute("""
            UPDATE complaints

            SET status = ?

            WHERE complaint_id = ?
        """, (
            new_status,
            complaint_id
        ))

        # Create notification for the citizen

        message = (
            "Your complaint "
            + complaint_id
            + " status has been updated to: "
            + new_status
        )

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn.execute("""
            INSERT INTO notifications
            (
                user_id,
                message,
                created_at
            )

            VALUES (?, ?, ?)
        """, (
            complaint["citizen_id"],
            message,
            created_at
        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for("police_complaints")
        )

    conn.close()

    return render_template(
        "update_complaint.html",
        complaint=complaint
    )


# ============================================================
# POLICE DASHBOARD
# ============================================================

@app.route("/police_dashboard")
def police_dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Police":

        return "Access Denied"


    return render_template(
        "police_dashboard.html",
        name=session["name"]
    )

# ============================================================
# ADMIN - VIEW USERS
# ============================================================

@app.route("/admin_users")
def admin_users():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Admin":
        return "Access Denied"

    conn = get_db_connection()

    users = conn.execute("""
        SELECT id, name, email, role
        FROM users
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_users.html",
        users=users
    )


# ============================================================
# ADMIN - VIEW ALL COMPLAINTS
# ============================================================

@app.route("/admin_complaints")
def admin_complaints():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Admin":
        return "Access Denied"

    conn = get_db_connection()

    complaints = conn.execute("""
        SELECT
            complaints.*,
            users.name AS citizen_name,
            users.email AS citizen_email

        FROM complaints

        JOIN users
        ON complaints.citizen_id = users.id

        ORDER BY complaints.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_complaints.html",
        complaints=complaints
    )


# ============================================================
# ADMIN - ANALYTICS
# ============================================================

@app.route("/admin_analytics")
def admin_analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Admin":
        return "Access Denied"

    conn = get_db_connection()

    total_complaints = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
    """).fetchone()[0]

    submitted = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Submitted'
    """).fetchone()[0]

    investigation = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Under Investigation'
    """).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
    """).fetchone()[0]

    closed = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Closed'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "admin_analytics.html",
        total_complaints=total_complaints,
        submitted=submitted,
        investigation=investigation,
        resolved=resolved,
        closed=closed
    )

# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin_dashboard")
def admin_dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))


    if session["role"] != "Admin":

        return "Access Denied"


    return render_template(
        "admin_dashboard.html",
        name=session["name"]
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    create_database()

    app.run(debug=True)