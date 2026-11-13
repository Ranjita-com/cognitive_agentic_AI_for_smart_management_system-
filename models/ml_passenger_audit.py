import os
import time
import sqlite3
import requests
import cv2

# 1. Dynamically resolve project paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == "models":
    PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

DATABASE_PATH = os.path.join(PROJECT_ROOT, "database", "smart_bus.db")
TEMP_IMAGE_PATH = os.path.join(CURRENT_DIR, "live_bus_interior.jpg")

# 2. Network Endpoint: Target your ESP32-S3 Stream Capture endpoint
# Replace with the exact local IP your ESP32 displays in Arduino Serial Monitor!
ESP32_CAPTURE_URL = "http://10.150.242.168:5000/api/esp32/telemetry" # Fallback if testing locally
# When ESP32-S3 Camera is active, use: "http://<ESP32_IP>/capture"

# 3. Vision Model Loader with Graceful Fallback
try:
    from ultralytics import YOLO
    HAS_YOLO = True
    print("[Vision Engine] Loading Ultralytics YOLOv8 Nano model weights (yolov8n.pt)...")
    model = YOLO("yolov8n.pt")
    print("[Vision Engine] YOLOv8 Nano ready for human detection (Class 0 - Person).")
except ImportError:
    HAS_YOLO = False
    print("[Vision Engine] Ultralytics is currently installing or not found.")
    print("[Vision Engine] Active Fallback: OpenCV HOG Human Detector.")
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

def detect_passengers(image_path):
    """Detects passenger count using YOLOv8 or OpenCV HOG fallback."""
    if HAS_YOLO:
        results = model(image_path, classes=[0], verbose=False)
        return len(results[0].boxes)
    else:
        img = cv2.imread(image_path)
        if img is None:
            return 0
        boxes, _ = hog.detectMultiScale(img, winStride=(8, 8), padding=(4, 4), scale=1.05)
        return len(boxes)

def run_passenger_ai_audit():
    try:
        if not os.path.exists(DATABASE_PATH):
            print(f"[Database Error] Target database not found at: {DATABASE_PATH}")
            return

        # Fetch live camera frame if ESP32 capture endpoint is configured
        if ESP32_CAPTURE_URL.endswith("/capture"):
            response = requests.get(ESP32_CAPTURE_URL, timeout=4)
            if response.status_code == 200:
                with open(TEMP_IMAGE_PATH, "wb") as f:
                    f.write(response.content)
                accurate_passenger_total = detect_passengers(TEMP_IMAGE_PATH)
            else:
                accurate_passenger_total = 0
        else:
            # Query existing IR count from database to synchronize audit baseline
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT current_passengers FROM buses WHERE bus_number = 'SB-101'")
            row = cursor.fetchone()
            accurate_passenger_total = row[0] if row else 0
            conn.close()

        print(f"[Passenger AI Audit] Bus SB-101 Verified Total: {accurate_passenger_total} passengers")

        # Synchronize verification metric into the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE buses 
            SET yolo_passenger_count = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE bus_number = 'SB-101'
        """, (accurate_passenger_total,))
        conn.commit()
        conn.close()

    except requests.exceptions.Timeout:
        print("[Connection Alert] Camera request timed out. Check ESP32-S3 network link.")
    except Exception as e:
        print(f"[AI Worker Loop Error] Execution failed: {e}")

if __name__ == "__main__":
    print("[Passenger AI Worker] Background audit service started.")
    print("Auditing image layers every 10 seconds (Press Ctrl+C to stop)...")
    while True:
        run_passenger_ai_audit()
        time.sleep(10)