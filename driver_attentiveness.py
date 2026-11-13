import cv2
import numpy as np
import dlib
from scipy.spatial import distance

# 1. Initialize Face Detector and Landmark Predictor
# Note: Ensure 'shape_predictor_68_face_landmarks.dat' is present from dlib's repository
detector = dlib.get_frontal_face_detector()
try:
    predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
except Exception:
    predictor = None

# Define indexes for landmarks based on the 68-point Dlib model
(l_start, l_end) = (42, 48)  # Left eye
(r_start, r_end) = (36, 42)  # Right eye
(m_start, m_end) = (48, 68)  # Mouth & lips

# Function to calculate Eye Aspect Ratio (EAR)
def eye_aspect_ratio(eye):
    # Compute Euclidean distances between the vertical eye landmarks
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    # Compute Euclidean distance between the horizontal eye landmarks
    C = distance.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C) if C > 0.001 else 0.30
    return ear

# Function to calculate Mouth Aspect Ratio (MAR) / Yawning
def mouth_aspect_ratio(mouth):
    # Vertical distances between upper and lower lips
    # Outer lips: points 51-59, 53-57 (relative index 3-9, 5-7), or inner lips
    A = distance.euclidean(mouth[3], mouth[9])   # Point 51 to Point 59
    B = distance.euclidean(mouth[2], mouth[10])  # Point 50 to Point 58
    C = distance.euclidean(mouth[4], mouth[8])   # Point 52 to Point 56
    # Horizontal distance between corners of mouth
    D = distance.euclidean(mouth[0], mouth[6])   # Point 48 to Point 54
    mar = (A + B + C) / (3.0 * D) if D > 0.001 else 0.15
    return mar

# Thresholds
EAR_THRESHOLD = 0.22  # Below this means eyes are closed / sleepy
MAR_THRESHOLD = 0.50  # Above this means mouth is wide open / yawning
CONSEC_FRAMES = 15    # Number of consecutive frames to trigger alert

counter_eyes = 0
counter_mouth = 0

# 2. Start Video Capture from Webcam
cap = cv2.VideoCapture(0)

print("Starting Driver Attention Monitoring (EAR + MAR)... Press 'q' to exit.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector(gray) if detector else []

    for face in faces:
        if predictor is None:
            break
        shape = predictor(gray, face)
        shape = np.array([[p.x, p.y] for p in shape.parts()])

        # Extract eye & mouth coordinates
        leftEye = shape[l_start:l_end]
        rightEye = shape[r_start:r_end]
        mouth = shape[m_start:m_end]

        # Calculate EAR & MAR
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        mar = mouth_aspect_ratio(mouth)

        # Draw contours
        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        mouthHull = cv2.convexHull(mouth)

        is_eyes_closed = (ear < EAR_THRESHOLD)
        is_mouth_open = (mar >= MAR_THRESHOLD)

        # Update counters
        if is_eyes_closed: counter_eyes += 1
        else: counter_eyes = 0

        if is_mouth_open: counter_mouth += 1
        else: counter_mouth = 0

        # Determine Driver Inactivity / Drowsiness State:
        # 1. FULLY INACTIVE: Eyes Closed AND Mouth Open Wide (Yawning), or prolonged severe closure
        if (counter_eyes >= 10 and is_mouth_open) or (counter_eyes >= 25 and counter_mouth >= 10):
            status_text = "CRITICAL: DRIVER FULLY INACTIVE (SWAP NEEDED!)"
            status_color = (0, 0, 255) # Red
            box_color = (0, 0, 255)
        # 2. SLIGHTLY INACTIVE: Only mouth open wide (yawning) OR only eyes closed
        elif is_eyes_closed or is_mouth_open or counter_eyes >= 10:
            status_text = "WARNING: DRIVER SLIGHTLY INACTIVE / DROWSY"
            status_color = (0, 165, 255) # Orange
            box_color = (0, 165, 255)
        # 3. ACTIVE: Normal eyes & mouth
        else:
            status_text = "STATUS: DRIVER ACTIVE & ATTENTIVE"
            status_color = (0, 255, 0) # Green
            box_color = (0, 255, 0)

        cv2.drawContours(frame, [leftEyeHull], -1, box_color, 1)
        cv2.drawContours(frame, [rightEyeHull], -1, box_color, 1)
        cv2.drawContours(frame, [mouthHull], -1, box_color, 1)

        # Display status banner & metrics
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2)
        cv2.putText(frame, f"EAR: {ear:.2f} ({'CLOSED' if is_eyes_closed else 'OPEN'})", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(frame, f"MAR: {mar:.2f} ({'YAWNING' if is_mouth_open else 'CLOSED'})", (10, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    cv2.imshow("Driver Attentiveness & Drowsiness Studio (EAR + MAR)", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()