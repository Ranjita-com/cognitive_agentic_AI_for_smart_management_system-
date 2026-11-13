import cv2
import os
from datetime import datetime

# -------------------------------------------------
# ESP32 CAMERA STREAM URL
# Change this IP to the IP shown in Arduino Serial Monitor
# -------------------------------------------------
ESP32_IP = "192.168.1.105"

STREAM_URL = f"http://{ESP32_IP}:81/stream"

# -------------------------------------------------
# Folder where video will be stored
# -------------------------------------------------
SAVE_FOLDER = r"C:\SmartBus\camera_data"

os.makedirs(SAVE_FOLDER, exist_ok=True)

# -------------------------------------------------
# Create video filename using current date/time
# -------------------------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

video_filename = os.path.join(
    SAVE_FOLDER,
    f"bus_camera_{timestamp}.avi"
)

print("Connecting to ESP32 camera...")
print("Stream:", STREAM_URL)

# -------------------------------------------------
# Open ESP32 camera stream
# -------------------------------------------------
cap = cv2.VideoCapture(STREAM_URL)

if not cap.isOpened():
    print("ERROR: Could not connect to ESP32 camera.")
    print("Check:")
    print("1. ESP32 is powered")
    print("2. ESP32 is connected to Wi-Fi")
    print("3. Laptop and ESP32 are on the same Wi-Fi")
    print("4. ESP32 IP address is correct")
    exit()

print("Camera connected successfully!")

# -------------------------------------------------
# Get camera resolution
# -------------------------------------------------
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print("Resolution:", width, "x", height)

# If ESP32 doesn't report resolution correctly,
# use a default resolution.
if width == 0 or height == 0:
    width = 640
    height = 480

# -------------------------------------------------
# Create video writer
# -------------------------------------------------
fourcc = cv2.VideoWriter_fourcc(*"MJPG")

fps = 10

out = cv2.VideoWriter(
    video_filename,
    fourcc,
    fps,
    (width, height)
)

print()
print("Recording started...")
print("Video will be saved at:")
print(video_filename)
print()
print("Press Q to stop recording.")

# -------------------------------------------------
# Capture frames
# -------------------------------------------------
while True:

    ret, frame = cap.read()

    if not ret:
        print("Could not receive frame from ESP32.")
        break

    # Display live camera
    cv2.imshow("ESP32 OV3660 Camera", frame)

    # Save frame to video
    out.write(frame)

    # Press Q to stop
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# -------------------------------------------------
# Release everything
# -------------------------------------------------
cap.release()
out.release()
cv2.destroyAllWindows()

print()
print("Recording stopped.")
print("Video saved successfully:")
print(video_filename)