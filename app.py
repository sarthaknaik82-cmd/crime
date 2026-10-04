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
# CREATE / UPDATE DATABASE
# ============================================================

def create_database():

    conn = get_db_connection()

    # --------------------------------------------------------
    # USERS TABLE
    # --------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # COMPLAINTS TABLE
    # --------------------------------------------------------

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
            fir_registered INTEGER DEFAULT 0,
            fir_number TEXT,
            police_remark TEXT,
            reviewed_at TEXT,
            FOREIGN KEY(citizen_id) REFERENCES users(id)
        )
    """)

    # --------------------------------------------------------
    # ADD NEW COLUMNS IF OLD DATABASE ALREADY EXISTS
    # --------------------------------------------------------

    columns = conn.execute(
        "PRAGMA table_info(complaints)"
    ).fetchall()

    existing_columns = [column["name"] for column in columns]

    if "fir_registered" not in existing_columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN fir_registered INTEGER DEFAULT 0
        """)

    if "fir_number" not in existing_columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN fir_number TEXT
        """)

    if "police_remark" not in existing_columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN police_remark TEXT
        """)

    if "reviewed_at" not in existing_columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN reviewed_at TEXT
        """)

    if "assigned_police_id" not in existing_columns:
        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN assigned_police_id INTEGER
        """)

    # --------------------------------------------------------
    # NOTIFICATIONS TABLE
    # --------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
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

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        if not name or not email or not password or not role:
            return render_template(
                "register.html",
                error="Please fill all the fields."
            )

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:

            conn.execute("""
                INSERT INTO users
                (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (
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

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["email"] = user["email"]

            if user["role"] == "Citizen":
                return redirect(url_for("citizen_dashboard"))

            elif user["role"] == "Police":
                return redirect(url_for("police_dashboard"))

            elif user["role"] == "Admin":
                return redirect(url_for("admin_dashboard"))

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
# SUBMIT COMPLAINT / REPORT INCIDENT
# ============================================================

@app.route("/report_crime", methods=["GET", "POST"])
def report_crime():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Citizen":
        return "Access Denied"

    if request.method == "POST":

        crime_type = request.form.get("crime_type", "").strip()
        incident_date = request.form.get("incident_date", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not crime_type:
            return render_template(
                "report_crime.html",
                error="Please select a crime type."
            )

        if not incident_date:
            return render_template(
                "report_crime.html",
                error="Please enter the incident date."
            )

        if not location:
            return render_template(
                "report_crime.html",
                error="Please enter the location."
            )

        if not description:
            return render_template(
                "report_crime.html",
                error="Please enter a description."
            )

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn = get_db_connection()

        # Temporary ID must be unique
        temporary_id = (
            "TEMP-" +
            datetime.now().strftime("%Y%m%d%H%M%S%f")
        )

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
                created_at,
                fir_registered
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            temporary_id,
            session["user_id"],
            crime_type,
            incident_date,
            location,
            description,
            "Submitted",
            created_at,
            0
        ))

        complaint_database_id = cursor.lastrowid

        # Generate proper complaint ID
        complaint_id = (
            "CR" +
            str(complaint_database_id).zfill(4)
        )

        conn.execute("""
            UPDATE complaints
            SET complaint_id = ?
            WHERE id = ?
        """, (
            complaint_id,
            complaint_database_id
        ))

        # Create notification
        message = (
            "Your complaint "
            + complaint_id
            + " has been submitted successfully "
              "and is pending police review."
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
            session["user_id"],
            message,
            created_at
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("notifications"))

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
    """, (
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

        complaint_id = request.form.get(
            "complaint_id",
            ""
        ).strip()

        conn = get_db_connection()

        complaint = conn.execute("""
            SELECT *
            FROM complaints
            WHERE complaint_id = ?
            AND citizen_id = ?
        """, (
            complaint_id,
            session["user_id"]
        )).fetchone()

        conn.close()

        if complaint is None:
            error = "Complaint not found."

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

    conn = get_db_connection()

    notifications_data = conn.execute("""
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "notifications.html",
        notifications=notifications_data
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
# POLICE - NEW COMPLAINTS
# ============================================================

@app.route("/police_complaints")
def police_complaints():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
        return "Access Denied"

    conn = get_db_connection()

    # Only new/unpicked complaints appear here.
    complaints = conn.execute("""
        SELECT
            complaints.*,
            users.name AS citizen_name,
            users.email AS citizen_email
        FROM complaints
        JOIN users ON complaints.citizen_id = users.id
        WHERE complaints.status = 'Submitted'
          AND complaints.assigned_police_id IS NULL
        ORDER BY complaints.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "police_complaints.html",
        complaints=complaints
    )


# ============================================================
# POLICE - PICK / ASSIGN A NEW COMPLAINT
# ============================================================

@app.route("/assign_complaint/<complaint_id>", methods=["POST"])
def assign_complaint(complaint_id):

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

    # Prevent two police officers from picking the same case.
    if complaint["status"] != "Submitted" or complaint["assigned_police_id"] is not None:
        conn.close()
        return "This complaint has already been picked."

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE complaints
        SET
            status = 'Assigned',
            assigned_police_id = ?,
            reviewed_at = ?
        WHERE complaint_id = ?
          AND status = 'Submitted'
          AND assigned_police_id IS NULL
    """, (
        session["user_id"],
        now,
        complaint_id
    ))

    # Notify the citizen that a police officer picked the case.
    conn.execute("""
        INSERT INTO notifications
        (user_id, message, created_at)
        VALUES (?, ?, ?)
    """, (
        complaint["citizen_id"],
        f"Your complaint {complaint_id} has been assigned to a police officer.",
        now
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("police_complaints"))


# ============================================================
# POLICE - ASSIGNED CASES
# ============================================================


@app.route("/assigned_cases")
def assigned_cases():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
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
        WHERE complaints.assigned_police_id = ?
        ORDER BY complaints.id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "assigned_cases.html",
        complaints=complaints
    )


# ============================================================
# POLICE - CASE INVESTIGATION
# ============================================================

@app.route("/case_investigation")
def case_investigation():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
        return "Access Denied"

    conn = get_db_connection()

    complaints = conn.execute("""
        SELECT
            complaints.*,
            users.name AS citizen_name,
            users.email AS citizen_email
        FROM complaints
        JOIN users ON complaints.citizen_id = users.id
        WHERE complaints.assigned_police_id = ?
          AND complaints.status IN (
              'Under Investigation',
              'FIR Registered',
              'No FIR / Closed',
              'Referred',
              'Resolved',
              'Closed'
          )
        ORDER BY complaints.id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "case_investigation.html",
        complaints=complaints
    )


# ============================================================
# POLICE - UPDATE COMPLAINT
# ============================================================

@app.route("/update_complaint/<complaint_id>", methods=["GET", "POST"])
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

    # Only the police officer who picked the case can update it.
    if complaint["assigned_police_id"] != session["user_id"]:
        conn.close()
        return "You are not assigned to this complaint."

    if request.method == "POST":

        new_status = request.form.get("status", "Assigned").strip()
        police_remark = request.form.get("police_remark", "").strip()

        allowed_statuses = {
            "Assigned",
            "Under Investigation",
            "FIR Registered",
            "No FIR / Closed",
            "Referred",
            "Resolved",
            "Closed"
        }

        if new_status not in allowed_statuses:
            conn.close()
            return "Invalid status"

        reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        fir_registered = complaint["fir_registered"] or 0
        fir_number = complaint["fir_number"]

        if new_status == "FIR Registered":
            fir_registered = 1
            if not fir_number:
                fir_number = "FIR" + str(complaint["id"]).zfill(4)

        elif new_status in ["No FIR / Closed", "Referred", "Closed"]:
            fir_registered = 0
            fir_number = None

        conn.execute("""
            UPDATE complaints
            SET
                status = ?,
                fir_registered = ?,
                fir_number = ?,
                police_remark = ?,
                reviewed_at = ?,
                assigned_police_id = ?
            WHERE complaint_id = ?
        """, (
            new_status,
            fir_registered,
            fir_number,
            police_remark,
            reviewed_at,
            session["user_id"],
            complaint_id
        ))

        if fir_registered == 1:
            message = (
                f"Your complaint {complaint_id} has been updated. "
                f"FIR No.: {fir_number}."
            )
        else:
            message = (
                f"Your complaint {complaint_id} status has been updated to: "
                f"{new_status}"
            )

        if police_remark:
            message += f" Remark: {police_remark}"

        conn.execute("""
            INSERT INTO notifications
            (user_id, message, created_at)
            VALUES (?, ?, ?)
        """, (
            complaint["citizen_id"],
            message,
            reviewed_at
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("case_investigation"))

    conn.close()

    return render_template(
        "update_complaint.html",
        complaint=complaint
    )

# ============================================================
# SINGLE ADMIN SETTINGS
# ============================================================

ADMIN_EMAIL = "sarthaknaik8222@gmail.com"


def check_admin():

    if "user_id" not in session:
        return False

    # Only the fixed admin email gets Admin access
    if session.get("email") != ADMIN_EMAIL:
        return False

    if session.get("role") != "Admin":
        return False

    return True

# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin_dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if not check_admin():
        return "Access Denied"

    return render_template(
        "admin_dashboard.html",
        name=session["name"]
    )


# ============================================================
# ADMIN - VIEW USERS
# ============================================================

@app.route("/admin_users")
def admin_users():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if not check_admin():
        return "Access Denied"

    conn = get_db_connection()

    users = conn.execute("""
        SELECT
            id,
            name,
            email,
            role
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

    if not check_admin():
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

    if not check_admin():
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
        WHERE status IN ('Closed', 'No FIR / Closed')
    """).fetchone()[0]

    fir_registered = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE fir_registered = 1
    """).fetchone()[0]

    conn.close()

    return render_template(
        "admin_analytics.html",
        total_complaints=total_complaints,
        submitted=submitted,
        investigation=investigation,
        resolved=resolved,
        closed=closed,
        fir_registered=fir_registered
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


@app.route("/debug_cases")
def debug_cases():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Police":
        return "Access Denied"

    conn = get_db_connection()

    complaints = conn.execute("""
        SELECT
            id,
            complaint_id,
            status,
            assigned_police_id,
            citizen_id
        FROM complaints
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return "<br>".join([
        f"ID={c['id']} | Complaint={c['complaint_id']} | "
        f"Status={c['status']} | "
        f"Assigned Police={c['assigned_police_id']} | "
        f"Citizen={c['citizen_id']}"
      
        for c in complaints
    ])
# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    create_database()

    app.run(debug=True)