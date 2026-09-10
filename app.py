import os
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import cv2
import numpy as np
from PIL import Image

app = Flask(__name__)

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/attendance_db")
client = MongoClient(MONGO_URI)
db = client.get_database()
attendance_collection = db["attendance"]

TOTAL_STUDENTS = 35
REFERENCE_FACE_PATH = "reference_face.jpg"

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

# Strict Face Verification Route
@app.route("/api/auth/verify-face", methods=["POST"])
def verify_face():
    if "live_photo" not in request.files:
        return jsonify({"success": False, "match": False, "message": "No photo provided"}), 400

    if not os.path.exists(REFERENCE_FACE_PATH):
        return jsonify({"success": False, "match": False, "message": "reference_face.jpg missing on server"}), 500

    try:
        # Load OpenCV Haar Cascade face detector
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)

        # 1. Process Reference Image
        ref_img = cv2.imread(REFERENCE_FACE_PATH)
        if ref_img is None:
            return jsonify({"success": False, "match": False, "message": "Could not read reference_face.jpg"}), 500

        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
        ref_faces = face_cascade.detectMultiScale(ref_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(ref_faces) == 0:
            return jsonify({"success": False, "match": False, "message": "No face found in reference_face.jpg"}), 500

        # Crop and normalize reference face
        rx, ry, rw, rh = ref_faces[0]
        ref_face_crop = ref_gray[ry:ry+rh, rx:rx+rw]
        ref_face_crop = cv2.resize(ref_face_crop, (150, 150))

        # 2. Process Live Uploaded Image
        file = request.files["live_photo"]
        live_bytes = np.frombuffer(file.read(), np.uint8)
        live_img = cv2.imdecode(live_bytes, cv2.IMREAD_COLOR)

        if live_img is None:
            return jsonify({"success": False, "match": False, "message": "Could not read camera frame"}), 400

        live_gray = cv2.cvtColor(live_img, cv2.COLOR_BGR2GRAY)
        live_faces = face_cascade.detectMultiScale(live_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(live_faces) == 0:
            return jsonify({"success": False, "match": False, "message": "No face detected in camera feed"}), 400

        # Crop and normalize live face
        lx, ly, lw, lh = live_faces[0]
        live_face_crop = live_gray[ly:ly+lh, lx:lx+lw]
        live_face_crop = cv2.resize(live_face_crop, (150, 150))

        # 3. Compare Facial Features
        ref_hist = cv2.calcHist([ref_face_crop], [0], None, [256], [0, 256])
        live_hist = cv2.calcHist([live_face_crop], [0], None, [256], [0, 256])

        cv2.normalize(ref_hist, ref_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(live_hist, live_hist, 0, 1, cv2.NORM_MINMAX)

        similarity = cv2.compareHist(ref_hist, live_hist, cv2.HISTCMP_CORREL)

        # High similarity score required to pass (0.75+)
        if similarity >= 0.75:
            return jsonify({"success": True, "match": True, "message": "Face verified successfully"}), 200
        else:
            return jsonify({"success": False, "match": False, "message": "Access Denied: Unrecognized face"}), 401

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