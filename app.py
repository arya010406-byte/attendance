import os
import sqlite3
from flask import Flask, render_template, request, jsonify
import numpy as np

app = Flask(__name__)

# HARDCODED TEACHER PIN
TEACHER_PIN = "1234"

# Path to pre-registered teacher face encoding (.npy file containing 128 floats)
FACE_ENCODING_PATH = 'teacher_face.npy'

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_num TEXT,
            division TEXT,
            date TEXT,
            roll_no TEXT,
            status TEXT,
            UNIQUE(class_num, division, date, roll_no)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Sample Student Data Generator
def get_sample_students(class_num, division):
    return [
        {"roll": "1", "name": "Ishaan Gupta"},
        {"roll": "2", "name": "Riya Sen"},
        {"roll": "3", "name": "Vihaan Das"},
        {"roll": "4", "name": "Tanvi Bhat"},
        {"roll": "5", "name": "Arjun Reddy"},
        {"roll": "6", "name": "Kavya Shah"}
    ]

@app.route('/')
def index():
    return render_template('index.html')

# LIGHTWEIGHT FACE VERIFICATION ROUTE (No C++ / dlib / OpenCV compilation needed)
@app.route('/api/verify-teacher', methods=['POST'])
def verify_teacher():
    try:
        if not os.path.exists(FACE_ENCODING_PATH):
            return jsonify({'success': False, 'message': 'Teacher face vector missing on server!'}), 500

        # Load registered teacher encoding array
        known_teacher_encoding = np.load(FACE_ENCODING_PATH)

        data = request.get_json()
        
        # Extract face vector sent from frontend
        incoming_encoding = data.get('descriptor')

        if not incoming_encoding:
            return jsonify({'success': False, 'message': 'No face features detected'}), 400

        incoming_vec = np.array(incoming_encoding, dtype=np.float64)

        # Fast Euclidean distance calculation using NumPy
        distance = np.linalg.norm(known_teacher_encoding - incoming_vec)

        # Strict Threshold check (0.45 or lower strictly limits access to registered face)
        if distance < 0.45:
            return jsonify({'success': True, 'message': 'Authentication successful'})
        else:
            return jsonify({'success': False, 'message': 'Access Denied: Unrecognized Face'}), 401

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# PIN BACKUP AUTHENTICATION ROUTE
@app.route('/api/verify-pin', methods=['POST'])
def verify_pin():
    data = request.get_json()
    entered_pin = data.get('pin')
    
    if entered_pin == TEACHER_PIN:
        return jsonify({'success': True, 'message': 'PIN Verification successful'})
    else:
        return jsonify({'success': False, 'message': 'Incorrect Security PIN'}), 401

# FETCH STUDENTS & RECORD STATUS ROUTE
@app.route('/api/students', methods=['GET'])
def get_students():
    class_num = request.args.get('class_num')
    division = request.args.get('division')
    date_str = request.args.get('date')

    students = get_sample_students(class_num, division)

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT roll_no, status FROM attendance WHERE class_num=? AND division=? AND date=?",
        (class_num, division, date_str)
    )
    records = dict(cursor.fetchall())
    conn.close()

    is_submitted = len(records) > 0

    student_list = []
    for s in students:
        status = records.get(s['roll'], 'Present')
        student_list.append({
            "roll": s['roll'],
            "name": s['name'],
            "status": status
        })

    return jsonify({
        'success': True,
        'students': student_list,
        'is_submitted': is_submitted,
        'is_holiday': False,
        'is_future': False
    })

# SAVE ATTENDANCE ROUTE
@app.route('/api/save-attendance', methods=['POST'])
def save_attendance():
    data = request.get_json()
    class_num = data.get('class_num')
    division = data.get('division')
    date_str = data.get('date')
    records = data.get('records')

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    try:
        for roll_no, status in records.items():
            cursor.execute('''
                INSERT INTO attendance (class_num, division, date, roll_no, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (class_num, division, date_str, roll_no, status))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Attendance saved successfully!'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Attendance already submitted for this date.'}), 400

# UPDATE ATTENDANCE ROUTE
@app.route('/api/update-attendance', methods=['POST'])
def update_attendance():
    data = request.get_json()
    class_num = data.get('class_num')
    division = data.get('division')
    date_str = data.get('date')
    records = data.get('records')

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    for roll_no, status in records.items():
        cursor.execute('''
            UPDATE attendance SET status=? 
            WHERE class_num=? AND division=? AND date=? AND roll_no=?
        ''', (status, class_num, division, date_str, roll_no))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Attendance updated successfully!'})

# ANALYTICS / GENERATE AVERAGE STATS ROUTE
@app.route('/api/generate-avg', methods=['GET'])
def generate_avg():
    class_num = request.args.get('class_num')
    division = request.args.get('division')

    students = get_sample_students(class_num, division)

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    avg_data = []
    for s in students:
        cursor.execute(
            "SELECT status FROM attendance WHERE class_num=? AND division=? AND roll_no=?",
            (class_num, division, s['roll'])
        )
        rows = cursor.fetchall()
        
        total = len(rows)
        present = sum(1 for r in rows if r[0] == 'Present')
        percentage = round((present / total) * 100) if total > 0 else 100

        avg_data.append({
            "roll": s['roll'],
            "name": s['name'],
            "present": present,
            "total": total if total > 0 else 1,
            "percentage": percentage
        })

    conn.close()
    return jsonify({'success': True, 'students': avg_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)