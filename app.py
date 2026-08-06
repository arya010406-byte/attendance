from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
import numpy as np
import base64
from datetime import datetime, timedelta
import cv2
import os
import certifi

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
TEACHER_PIN = "5024"
MONGO_URI = "mongodb+srv://arya010406_db_user:cm1dSXahpmAmNf82@cluster0.6zhgx9u.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# --- LAZY INITIALIZERS ---
db_client = None
face_cascade = None

def get_collection():
    global db_client
    if db_client is None:
        db_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    return db_client["school_db"]["attendance"]

def get_face_cascade():
    global face_cascade
    if face_cascade is None:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    return face_cascade

# --- HELPER: HOLIDAY CHECKER ---
def is_holiday(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()
    
    if weekday == 6:
        return True, "Sunday Holiday"
    
    if weekday == 5:
        day_of_month = dt.day
        saturday_index = (day_of_month - 1) // 7 + 1
        if saturday_index in [2, 4]:
            return True, f"{saturday_index}nd/th Saturday Holiday"
            
    return False, ""

# --- UNIQUE NAME GENERATOR ---
FIRST_NAMES = [
    "Aarav", "Ananya", "Rohan", "Priya", "Kabir", "Diya", "Vivaan", "Anushka", "Aditya", "Sanya",
    "Ishaan", "Riya", "Vihaan", "Tanvi", "Arjun", "Kavya", "Ayaan", "Meera", "Dhruv", "Pooja",
    "Karan", "Sneha", "Siddharth", "Nisha", "Rahul", "Neha", "Yash", "Tara", "Varun", "Kriti"
]

LAST_NAMES = [
    "Sharma", "Patel", "Verma", "Singh", "Mehta", "Joshi", "Kapoor", "Nair", "Rao", "Malhotra",
    "Gupta", "Sen", "Das", "Bhat", "Reddy", "Shah", "Khan", "Iyer", "Saxena", "Hegde",
    "Gill", "Roy", "Bose", "Agarwal", "Mishra", "Chawla", "Thakur", "Sutaria", "Dhawan", "Sanon"
]

def generate_unique_students(class_num, division):
    students = []
    div_offset = ord(division.upper()) - ord('A')
    class_offset = int(class_num)
    
    for i in range(1, 31):
        fn_idx = (i - 1 + class_offset) % len(FIRST_NAMES)
        ln_idx = (i - 1 + div_offset * 3 + class_offset) % len(LAST_NAMES)
        name = f"{FIRST_NAMES[fn_idx]} {LAST_NAMES[ln_idx]}"
        students.append({"id": i, "roll": str(i), "name": name})
    return students

# --- API ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/students', methods=['GET'])
def get_students():
    class_num = request.args.get('class_num', '10')
    division = request.args.get('division', 'A')
    selected_date = request.args.get('date')
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    is_future = selected_date > today_str
    
    holiday, reason = is_holiday(selected_date)
    
    attendance_collection = get_collection()
    records = list(attendance_collection.find({
        "class_num": class_num,
        "division": division,
        "date": selected_date
    }))

    saved_records = {str(doc['student_roll']): doc['status'] for doc in records}
    is_submitted = len(records) > 0

    master_list = generate_unique_students(class_num, division)
    formatted_students = []

    for s in master_list:
        status = saved_records.get(s['roll'], 'Present') if is_submitted else 'Present'
        formatted_students.append({
            "id": s['id'],
            "name": s['name'],
            "roll": s['roll'],
            "status": status
        })
        
    return jsonify({
        "success": True, 
        "students": formatted_students,
        "is_submitted": is_submitted,
        "is_holiday": holiday,
        "holiday_reason": reason,
        "is_future": is_future
    })

@app.route('/api/generate-avg', methods=['GET'])
def generate_avg():
    class_num = request.args.get('class_num', '10')
    division = request.args.get('division', 'A')
    selected_date = request.args.get('date')
    avg_type = request.args.get('type', 'week')
    
    ref_date = datetime.strptime(selected_date, "%Y-%m-%d")
    
    if avg_type == 'week':
        start_date = (ref_date - timedelta(days=6)).strftime("%Y-%m-%d")
        query = {
            "class_num": class_num,
            "division": division,
            "date": {"$gte": start_date, "$lte": selected_date}
        }
    else:
        month_prefix = ref_date.strftime("%Y-%m")
        query = {
            "class_num": class_num,
            "division": division,
            "date": {"$regex": f"^{month_prefix}"}
        }
    
    attendance_collection = get_collection()
    records = list(attendance_collection.find(query))
    students_list = generate_unique_students(class_num, division)
    
    student_stats = []
    for student in students_list:
        roll = int(student['roll'])
        student_records = [r for r in records if r['student_roll'] == roll]
        
        total_days = len(student_records)
        present_days = sum(1 for r in student_records if r['status'] == 'Present')
        
        pct = round((present_days / total_days) * 100, 1) if total_days > 0 else 0.0
        
        student_stats.append({
            "roll": student['roll'],
            "name": student['name'],
            "present": present_days,
            "total": total_days,
            "percentage": pct
        })

    return jsonify({"success": True, "students": student_stats})

@app.route('/api/verify-pin', methods=['POST'])
def verify_pin():
    entered_pin = request.json.get('pin', '')
    if entered_pin == TEACHER_PIN:
        return jsonify({"success": True, "message": "PIN Verified"}), 200
    return jsonify({"success": False, "message": "Incorrect PIN!"}), 401

@app.route('/api/verify-teacher', methods=['POST'])
def verify_teacher():
    try:
        image_data = request.json.get('image', '').split(',')[1]
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = get_face_cascade()
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            return jsonify({"success": True, "message": "Teacher Verified"}), 200

        return jsonify({"success": False, "message": "Face Not Recognized!"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": f"Verification error: {str(e)}"}), 400

@app.route('/api/save-attendance', methods=['POST'])
def save_attendance():
    data = request.json
    class_num = data.get('class_num')
    division = data.get('division')
    selected_date = data.get('date')
    records = data.get('records')
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    if selected_date > today_str:
        return jsonify({"success": False, "message": "Cannot record attendance for a future date!"}), 400
    
    holiday, reason = is_holiday(selected_date)
    if holiday:
        return jsonify({"success": False, "message": f"Cannot save attendance: {reason}"}), 400

    attendance_collection = get_collection()
    existing = attendance_collection.find_one({
        "class_num": class_num,
        "division": division,
        "date": selected_date
    })
    
    if existing:
        return jsonify({"success": False, "message": "Attendance already submitted!"}), 400
        
    students_list = generate_unique_students(class_num, division)
    name_map = {str(s['roll']): s['name'] for s in students_list}

    documents_to_insert = [{
        "class_num": class_num,
        "division": division,
        "date": selected_date,
        "student_roll": int(roll),
        "student_name": name_map.get(str(roll), "Unknown Student"),
        "status": status
    } for roll, status in records.items()]
        
    if documents_to_insert:
        attendance_collection.insert_many(documents_to_insert)

    return jsonify({"success": True, "message": "Attendance saved to MongoDB Atlas!"})

@app.route('/api/update-attendance', methods=['POST'])
def update_attendance():
    data = request.json
    class_num = data.get('class_num')
    division = data.get('division')
    selected_date = data.get('date')
    records = data.get('records')
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    if selected_date > today_str:
        return jsonify({"success": False, "message": "Cannot update attendance for a future date!"}), 400

    attendance_collection = get_collection()
    students_list = generate_unique_students(class_num, division)
    name_map = {str(s['roll']): s['name'] for s in students_list}

    for roll, status in records.items():
        attendance_collection.update_one(
            {"class_num": class_num, "division": division, "date": selected_date, "student_roll": int(roll)},
            {"$set": {"student_name": name_map.get(str(roll), "Unknown Student"), "status": status}},
            upsert=True
        )

    return jsonify({"success": True, "message": "Attendance updated successfully!"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)