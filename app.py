from flask import Flask, request, jsonify
import face_recognition
import numpy as np

app = Flask(__name__)

# Load your face image once at startup
reference_image = face_recognition.load_image_file("reference.jpg")
reference_encodings = face_recognition.face_encodings(reference_image)

if len(reference_encodings) > 0:
    my_face_encoding = reference_encodings[0]
else:
    raise Exception("Could not find a face in reference.jpg!")

@app.route('/api/auth/verify-face', methods=['POST'])
def verify_face():
    if 'live_photo' not in request.files:
        return jsonify({"success": False, "message": "No image uploaded"}), 400

    file = request.files['live_photo']
    live_image = face_recognition.load_image_file(file)
    live_encodings = face_recognition.face_encodings(live_image)

    if len(live_encodings) == 0:
        return jsonify({"success": False, "match": False, "message": "No face detected in camera!"})

    # Compare live face to saved face
    matches = face_recognition.compare_faces([my_face_encoding], live_encodings[0], tolerance=0.5)

    if matches[0]:
        return jsonify({"success": True, "match": True})
    else:
        return jsonify({"success": False, "match": False, "message": "Access Denied: Unrecognized face!"})

if __name__ == '__main__':
    app.run(port=5000)