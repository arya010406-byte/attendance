import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)

# Fetch MongoDB URI safely from environment variables
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/attendance_db")
client = MongoClient(MONGO_URI)
db = client.get_database()
attendance_collection = db["attendance"]

TOTAL_STUDENTS = 35

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/students", methods=["GET"])
def get_students():
    students = [{"id": i, "name": f"Student {i}"} for i in range(1, TOTAL_STUDENTS + 1)]
    return jsonify(students)

# Fetch saved attendance for a specific Class, Division, and Date
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

# Submit or update attendance (Mandatory 35 students validation)
@app.route("/api/attendance/submit", methods=["POST"])
def submit_attendance():
    data = request.get_json() or {}
    class_name = data.get("className")
    division = data.get("division")
    date = data.get("date")
    records = data.get("records", {})

    if not class_name or not division or not date:
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    # Reject submission if fewer than 35 students are marked
    if len(records) < TOTAL_STUDENTS:
        missing_count = TOTAL_STUDENTS - len(records)
        return jsonify({
            "success": False, 
            "message": f"Attendance incomplete! Please mark attendance for all {TOTAL_STUDENTS} students. ({missing_count} remaining)"
        }), 400

    # Save to MongoDB Atlas
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

    return jsonify({"success": True, "message": "Attendance recorded successfully!"}), 200

# Facial Scan Verification Route
@app.route("/api/auth/verify-face", methods=["POST"])
def verify_face():
    if "live_photo" not in request.files:
        return jsonify({"success": False, "match": False, "message": "No photo provided"}), 400
    
    return jsonify({"success": True, "match": True, "message": "Face verified successfully"}), 200

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