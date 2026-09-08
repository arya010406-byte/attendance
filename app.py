import os
import io
import webbrowser
from datetime import datetime, timedelta
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from pymongo import MongoClient
import face_recognition

app = Flask(__name__)
CORS(app)

REFERENCE_IMAGE_PATH = "reference_face.jpg"

# MongoDB Atlas Setup (URL Encoded Password for Special Characters)
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://arya010406_db_user:%26A3kdw.%25FyH%24w6p@cluster0.cqlyxu5.mongodb.net/schoolDB?retryWrites=true&w=majority&appName=Cluster0"
)
client = MongoClient(MONGO_URI)
db = client.get_database()
attendance_collection = db["attendances"]

# Helper function to locate index.html
def find_index_file():
    root_index = os.path.join(os.getcwd(), 'index.html')
    public_index = os.path.join(os.getcwd(), 'public', 'index.html')
    if os.path.exists(root_index):
        return root_index
    elif os.path.exists(public_index):
        return public_index
    return None

# Serve Homepage (index.html)
@app.route('/')
def index():
    index_path = find_index_file()
    if index_path:
        return send_file(index_path)
    return "<h1>Error: index.html not found!</h1><p>Please place index.html in the same directory as app.py.</p>", 404

# Direct Face Verification API
@app.route('/api/auth/verify-face', methods=['POST'])
def verify_face():
    if not os.path.exists(REFERENCE_IMAGE_PATH):
        return jsonify({"success": False, "match": False, "message": "No reference face found! Run rgt.py first to capture your face."}), 400

    if 'live_photo' not in request.files:
        return jsonify({"success": False, "match": False, "message": "No live scan photo received."}), 400

    try:
        ref_image = face_recognition.load_image_file(REFERENCE_IMAGE_PATH)
        ref_encodings = face_recognition.face_encodings(ref_image)

        if not ref_encodings:
            return jsonify({"success": False, "match": False, "message": "No clear face found in saved reference image."}), 400

        file_bytes = request.files['live_photo'].read()
        live_image = face_recognition.load_image_file(io.BytesIO(file_bytes))
        live_encodings = face_recognition.face_encodings(live_image)

        if not live_encodings:
            return jsonify({"success": False, "match": False, "message": "No face detected in live video scan!"}), 400

        distance = float(face_recognition.face_distance([ref_encodings[0]], live_encodings[0])[0])
        is_match = distance <= 0.45

        if is_match:
            return jsonify({"success": True, "match": True, "distance": distance, "message": "Face Verified!"})
        else:
            return jsonify({"success": False, "match": False, "distance": distance, "message": "Face Mismatch: Access Denied!"}), 401

    except Exception as e:
        return jsonify({"success": False, "match": False, "message": str(e)}), 500

# Save Attendance to MongoDB Atlas
@app.route('/api/attendance/submit', methods=['POST'])
def submit_attendance():
    try:
        data = request.json
        class_name = data.get("className")
        division = data.get("division")
        date = data.get("date")
        records = data.get("records")

        query = {"className": class_name, "division": division, "date": date}
        update = {"$set": {"className": class_name, "division": division, "date": date, "records": records}}

        attendance_collection.update_one(query, update, upsert=True)
        return jsonify({"success": True, "message": "Attendance register saved to MongoDB Atlas!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Fetch Attendance from MongoDB Atlas
@app.route('/api/attendance/<class_name>/<division>/<date>', methods=['GET'])
def get_attendance(class_name, division, date):
    try:
        record = attendance_collection.find_one({"className": class_name, "division": division, "date": date}, {"_id": 0})
        if record:
            return jsonify({"success": True, "record": record})
        return jsonify({"success": False, "message": "No record found."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Fetch Average Attendance Breakdown (Week / Month for all 35 Students)
@app.route('/api/attendance/average', methods=['GET'])
def get_attendance_average():
    try:
        class_name = request.args.get('class')
        division = request.args.get('division')
        ref_date_str = request.args.get('date')
        timeframe = request.args.get('timeframe')

        ref_date = datetime.strptime(ref_date_str, '%Y-%m-%d')

        if timeframe == 'week':
            start_date = ref_date - timedelta(days=7)
        else:
            start_date = ref_date - timedelta(days=30)

        records = list(attendance_collection.find({
            "className": class_name,
            "division": division,
            "date": {"$gte": start_date.strftime('%Y-%m-%d'), "$lte": ref_date_str}
        }))

        days_count = len(records)
        if days_count == 0:
            return jsonify({"success": False, "message": "No historical attendance records found for this period."}), 404

        student_counts = {str(i): 0 for i in range(1, 36)}

        for record in records:
            rec_data = record.get('records', {})
            for roll_no, status in rec_data.items():
                if status in ['Present', 'Late']:
                    student_counts[str(roll_no)] = student_counts.get(str(roll_no), 0) + 1

        averages = {}
        for roll_no, attended_days in student_counts.items():
            averages[roll_no] = round((attended_days / days_count) * 100, 1)

        return jsonify({"success": True, "averages": averages, "daysCount": days_count})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Serve Static Assets
@app.route('/<path:filename>')
def static_files(filename):
    if os.path.exists(os.path.join(os.getcwd(), filename)):
        return send_from_directory(os.getcwd(), filename)
    elif os.path.exists(os.path.join(os.getcwd(), 'public', filename)):
        return send_from_directory(os.path.join(os.getcwd(), 'public'), filename)
    return "File not found", 404

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("Starting School Attendance Portal...")
    Timer(1.2, open_browser).start()
    app.run(host='127.0.0.1', port=5000, debug=False)