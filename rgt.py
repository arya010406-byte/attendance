import cv2
import face_recognition
import numpy as np

def register_teacher():
    print("Opening webcam... Look at the camera and press 's' to save your face, or 'q' to quit.")
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to access camera.")
            break

        # Show live feed
        cv2.imshow("Register Teacher Face - Press 's' to Save", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_frame)

            if len(encodings) > 0:
                np.save("teacher_face.npy", encodings[0])
                print("✓ Teacher face successfully registered and saved to 'teacher_face.npy'!")
                break
            else:
                print("⚠️ No face detected. Please align your face and press 's' again.")

        elif key == ord('q'):
            print("Registration canceled.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    register_teacher()