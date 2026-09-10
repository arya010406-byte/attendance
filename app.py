import face_recognition
from PIL import Image
import io

# Load and encode your reference face once during startup
MY_FACE_PATH = "my_face.jpg"
MY_FACE_ENCODING = None

if os.path.exists(MY_FACE_PATH):
    reference_image = face_recognition.load_image_file(MY_FACE_PATH)
    encodings = face_recognition.face_encodings(reference_image)
    if encodings:
        MY_FACE_ENCODING = encodings[0]
        print("Reference face encoded successfully.")
    else:
        print("WARNING: No face found in reference image!")
else:
        print("WARNING: Reference face image ('my_face.jpg') not found!")

@app.route("/api/auth/verify-face", methods=["POST"])
def verify_face():
    if "live_photo" not in request.files:
        return jsonify({"success": False, "match": False, "message": "No photo provided"}), 400

    if MY_FACE_ENCODING is None:
        return jsonify({"success": False, "match": False, "message": "Reference face not configured on server"}), 500

    try:
        # Load live image from request buffer
        file = request.files["live_photo"]
        live_image = face_recognition.load_image_file(io.BytesIO(file.read()))
        
        # Locate and encode faces in live photo
        live_encodings = face_recognition.face_encodings(live_image)

        if not live_encodings:
            return jsonify({"success": False, "match": False, "message": "No face detected in live photo"}), 400

        # Compare the live face to your encoded face (tolerance: lower = stricter)
        matches = face_recognition.compare_faces([MY_FACE_ENCODING], live_encodings[0], tolerance=0.5)

        if matches[0]:
            return jsonify({"success": True, "match": True, "message": "Face verified successfully"}), 200
        else:
            return jsonify({"success": False, "match": False, "message": "Access Denied: Unrecognized face"}), 401

    except Exception as e:
        return jsonify({"success": False, "match": False, "message": f"Processing error: {str(e)}"}), 500