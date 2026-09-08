import cv2
import os

REFERENCE_IMAGE_PATH = "reference_face.jpg"

def capture_reference_face():
    print("Opening camera... Press 'SPACE' to capture your face, or 'ESC' to exit.")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Unable to access the camera.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab camera frame.")
            break

        cv2.imshow("Press SPACE to Save Face | ESC to Cancel", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 32:  # SPACEBAR
            cv2.imwrite(REFERENCE_IMAGE_PATH, frame)
            print(f"Success! Reference face saved as '{REFERENCE_IMAGE_PATH}'. Exiting...")
            break
        elif key == 27:  # ESC
            print("Cancelled face registration.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    capture_reference_face()