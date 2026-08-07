import base64
import os
import sqlite3

import cv2
import face_recognition
from flask import Flask, jsonify, render_template, request
import numpy as np

app = Flask(__name__)

TEACHER_PIN = "1234"
FACE_ENCODING_PATH = "teacher_face.npy"


def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_num TEXT,
            division TEXT,
            date TEXT,
            roll_no TEXT,
            status TEXT,
            UNIQUE(class_num, division, date, roll_no)
        )
    """
    )
    conn.commit()
    conn.close()


init_db()


def get_sample_students(class_num, division):
    return [
        {"roll": "1", "name": "Ishaan Gupta"},
        {"roll": "2", "name": "Riya Sen"},
        {"roll": "3", "name": "Vihaan Das"},
        {"roll": "4", "name": "Tanvi Bhat"},
        {"roll": "5", "name": "Arjun Reddy"},
        {"roll": "6", "name": "Kavya Shah"},
    ]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/verify-teacher", methods=["POST"])
def verify_teacher():
    try:
        if not os.path.exists(FACE_ENCODING_PATH):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Teacher face encoding missing on server!",
                    }
                ),
                500,
            )

        known_teacher_encoding = np.load(FACE_ENCODING_PATH)

        data = request.get_json()
        image_data = data.get("image")

        if not image_data:
            return (
                jsonify({"success": False, "message": "No image captured"}),
                400,
            )

        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        face_encodings = face_recognition.face_encodings(rgb_img)

        if len(face_encodings) == 0:
            return (
                jsonify(
                    {"success": False, "message": "No face detected in camera"}
                ),
                400,
            )

        incoming_encoding = face_encodings[0]
        face_distance = face_recognition.face_distance(
            [known_teacher_encoding], incoming_encoding
        )[0]

        if face_distance < 0.45:
            return jsonify(
                {"success": True, "message": "Authentication successful"}
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Access Denied: Unrecognized Face",
                    }
                ),
                401,
            )

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@app.route("/api/verify-pin", methods=["POST"])
def verify_pin():
    data = request.get_json()
    if data.get("pin") == TEACHER_PIN:
        return jsonify(
            {"success": True, "message": "PIN Verification successful"}
        )
    return jsonify({"success": False, "message": "Incorrect Security PIN"}), 401


@app.route("/api/students", methods=["GET"])
def get_students():
    class_num = request.args.get("class_num")
    division = request.args.get("division")
    date_str = request.args.get("date")

    students = get_sample_students(class_num, division)

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT roll_no, status FROM attendance WHERE class_num=? AND division=? AND date=?",
        (class_num, division, date_str),
    )
    records = dict(cursor.fetchall())
    conn.close()

    student_list = [
        {"roll": s["roll"], "name": s["name"], "status": records.get(s["roll"], "Present")}
        for s in students
    ]

    return jsonify(
        {
            "success": True,
            "students": student_list,
            "is_submitted": len(records) > 0,
            "is_holiday": False,
            "is_future": False,
        }
    )


@app.route("/api/save-attendance", methods=["POST"])
def save_attendance():
    data = request.get_json()
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    try:
        for roll_no, status in data.get("records", {}).items():
            cursor.execute(
                """
                INSERT INTO attendance (class_num, division, date, roll_no, status)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    data.get("class_num"),
                    data.get("division"),
                    data.get("date"),
                    roll_no,
                    status,
                ),
            )
        conn.commit()
        conn.close()
        return jsonify(
            {"success": True, "message": "Attendance saved successfully!"}
        )
    except sqlite3.IntegrityError:
        conn.close()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Attendance already submitted for this date.",
                }
            ),
            400,
        )


@app.route("/api/update-attendance", methods=["POST"])
def update_attendance():
    data = request.get_json()
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    for roll_no, status in data.get("records", {}).items():
        cursor.execute(
            """
            UPDATE attendance SET status=? 
            WHERE class_num=? AND division=? AND date=? AND roll_no=?
        """,
            (
                status,
                data.get("class_num"),
                data.get("division"),
                data.get("date"),
                roll_no,
            ),
        )

    conn.commit()
    conn.close()
    return jsonify(
        {"success": True, "message": "Attendance updated successfully!"}
    )


@app.route("/api/generate-avg", methods=["GET"])
def generate_avg():
    class_num = request.args.get("class_num")
    division = request.args.get("division")
    students = get_sample_students(class_num, division)

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    avg_data = []
    for s in students:
        cursor.execute(
            "SELECT status FROM attendance WHERE class_num=? AND division=? AND roll_no=?",
            (class_num, division, s["roll"]),
        )
        rows = cursor.fetchall()
        total = len(rows)
        present = sum(1 for r in rows if r[0] == "Present")
        avg_data.append(
            {
                "roll": s["roll"],
                "name": s["name"],
                "present": present,
                "total": total if total > 0 else 1,
                "percentage": round((present / total) * 100) if total > 0 else 100,
            }
        )

    conn.close()
    return jsonify({"success": True, "students": avg_data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)