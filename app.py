import os
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import numpy as np
import face_recognition

app = Flask(__name__)

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/attendance_db")
client = MongoClient(MONGO_URI)
db = client.get_database()
attendance_collection = db["attendance"]

TOTAL_STUDENTS = 35
REFERENCE_FACE_PATH = "reference_face.jpg"

# face_recognition compares faces using Euclidean distance between 128-d
# embeddings. LOWER distance = more similar. 0.6 is the library's own
# general-purpose default; 0.45-0.5 is stricter and recommended here since
# this gates access rather than just tagging photos. Tune down further
# (e.g. 0.40) if a look-alike or photo of a photo is getting through;
# tune up slightly (e.g. 0.50) if the real user is being rejected too often.
MATCH_DISTANCE_THRESHOLD = 0.45

# Load and encode the reference face once at startup instead of on every
# request. If this fails, the app should not silently allow logins, so we
# fail loudly here.
REFERENCE_ENCODING = None


def _load_reference_encoding():
    if not os.path.exists(REFERENCE_FACE_PATH):
        raise RuntimeError(
            f"Reference face not found at '{REFERENCE_FACE_PATH}'. Run rgt.py to register one."
        )
    ref_img = face_recognition.load_image_file(REFERENCE_FACE_PATH)
    encodings = face_recognition.face_encodings(ref_img)
    if not encodings:
        raise RuntimeError(
            "No face detected in the reference image. Re-capture reference_face.jpg "
            "with a clear, front-facing, well-lit photo."
        )
    if len(encodings) > 1:
        raise RuntimeError(
            "Multiple faces detected in the reference image. It must contain exactly one face."
        )
    return encodings[0]


try:
    REFERENCE_ENCODING = _load_reference_encoding()
except RuntimeError as e:
    # Don't crash import (so /api/students etc. still work), but log clearly.
    print(f"[verify-face] WARNING: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/students", methods=["GET"])
def get_students():
    students = [{"id": i, "name": f"Student {i}"} for i in range(1, TOTAL_STUDENTS + 1)]
    return jsonify(students)


# Fetch attendance for a specific Class, Division, and Date
@app.route("/api/attendance/<className>/<division>/<date>", methods=["GET"])
def get_attendance(className, division, date):
    record = attendance_collection.find_one({
        "className": str(className),
        "division": str(division),
        "date": str(date)
    }, {"_id": 0})

    if record:
        return jsonify({"success": True, "record": record}), 200
    return jsonify({"success": False, "message": "No record found"}), 404


# Submit or update attendance with strict 35-student check
@app.route("/api/attendance/submit", methods=["POST"])
def submit_attendance():
    data = request.get_json() or {}
    class_name = data.get("className")
    division = data.get("division")
    date = data.get("date")
    records = data.get("records", {})

    if not class_name or not division or not date:
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    if len(records) < TOTAL_STUDENTS:
        missing_count = TOTAL_STUDENTS - len(records)
        return jsonify({
            "success": False,
            "message": f"Attendance incomplete! Please mark all {TOTAL_STUDENTS} students. ({missing_count} remaining)"
        }), 400

    attendance_entry = {
        "className": str(class_name),
        "division": str(division),
        "date": str(date),
        "records": records
    }

    attendance_collection.update_one(
        {"className": str(class_name), "division": str(division), "date": str(date)},
        {"$set": attendance_entry},
        upsert=True
    )

    return jsonify({"success": True, "message": "Saved to MongoDB Atlas successfully!"}), 200


# Face Verification Route
@app.route("/api/auth/verify-face", methods=["POST"])
def verify_face():
    if "live_photo" not in request.files:
        return jsonify({"success": False, "match": False, "message": "No photo provided"}), 400

    # No reference on file / couldn't be encoded -> hard failure, never a silent pass.
    if REFERENCE_ENCODING is None:
        try:
            reference_encoding = _load_reference_encoding()
        except RuntimeError as e:
            return jsonify({"success": False, "match": False, "message": str(e)}), 500
    else:
        reference_encoding = REFERENCE_ENCODING

    try:
        file = request.files["live_photo"]
        live_bytes = file.read()

        # face_recognition wants a numpy RGB image array
        live_array = np.frombuffer(live_bytes, np.uint8)
        import cv2  # local import kept minimal; only used for decoding the upload
        live_bgr = cv2.imdecode(live_array, cv2.IMREAD_COLOR)
        if live_bgr is None or live_bgr.size == 0:
            return jsonify({"success": False, "match": False, "message": "Invalid camera feed"}), 400
        live_rgb = cv2.cvtColor(live_bgr, cv2.COLOR_BGR2RGB)

        live_face_locations = face_recognition.face_locations(live_rgb)
        if not live_face_locations:
            return jsonify({
                "success": True,
                "match": False,
                "message": "No face detected in the photo. Center your face and ensure good lighting."
            }), 200

        if len(live_face_locations) > 1:
            return jsonify({
                "success": True,
                "match": False,
                "message": "Multiple faces detected. Only one person should be in frame."
            }), 200

        live_encodings = face_recognition.face_encodings(live_rgb, known_face_locations=live_face_locations)
        live_encoding = live_encodings[0]

        distance = face_recognition.face_distance([reference_encoding], live_encoding)[0]
        is_match = bool(distance <= MATCH_DISTANCE_THRESHOLD)

        return jsonify({
            "success": True,
            "match": is_match,
            "message": (
                f"Face verified successfully (distance={distance:.3f})"
                if is_match else
                f"Face does not match reference (distance={distance:.3f})"
            )
        }), 200

    except Exception as e:
        return jsonify({"success": False, "match": False, "message": f"Verification error: {str(e)}"}), 500


# Calculate Historical Average Attendance
@app.route("/api/attendance/average", methods=["GET"])
def get_attendance_average():
    class_name = request.args.get("class")
    division = request.args.get("division")
    date_str = request.args.get("date")
    timeframe = request.args.get("timeframe", "week")

    if not class_name or not division or not date_str:
        return jsonify({"success": False, "message": "Missing parameters"}), 400

    try:
        end_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "message": "Invalid date format"}), 400

    days_offset = 7 if timeframe == "week" else 30
    start_date = end_date - timedelta(days=days_offset)

    query = {
        "className": str(class_name),
        "division": str(division),
        "date": {"$gte": start_date.strftime("%Y-%m-%d"), "$lte": date_str}
    }

    records_cursor = list(attendance_collection.find(query, {"_id": 0}))
    days_count = len(records_cursor)

    if days_count == 0:
        return jsonify({"success": False, "message": f"No records found for this {timeframe}."}), 404

    student_stats = {str(i): {"present_count": 0} for i in range(1, TOTAL_STUDENTS + 1)}

    for entry in records_cursor:
        rec = entry.get("records", {})
        for roll_no, status in rec.items():
            if status in ["Present", "Late"] and roll_no in student_stats:
                student_stats[roll_no]["present_count"] += 1

    averages = {}
    for roll_no, data in student_stats.items():
        rate = round((data["present_count"] / days_count) * 100, 1)
        averages[int(roll_no)] = rate

    return jsonify({
        "success": True,
        "daysCount": days_count,
        "averages": averages
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)