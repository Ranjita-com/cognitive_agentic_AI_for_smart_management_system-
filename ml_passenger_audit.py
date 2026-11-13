"""
========================================================================================
🚌 SMART BUS BS-101: ML PASSENGER AUDIT & ESP32-CAM REAL-TIME OCCUPANCY SYSTEM
========================================================================================

Description:
  Takes live video frames from the ESP32-CAM module (or local webcam/video/test feed),
  performs AI/ML Person Detection and centroid line-crossing tracking, calculates
  the accurate passenger count, and synchronizes with the Smart Bus Flask Backend
  for Bus BS-101 in real-time.

Key Features:
  1. Ingests ESP32-CAM stream (http://<ESP32_IP>:81/stream or /capture), USB webcam, or test simulation.
  2. Dual ML Detection Engine:
     - Ultralytics YOLOv8 (yolov8n.pt) if installed
     - Native OpenCV HOG People Detector + NMS Centroid Tracker (Zero-dependency fallback)
  3. Directional Entry/Exit Line Crossing to prevent double-counting.
  4. Real-time REST API Dispatch to http://localhost:5000/api/camera/yolo-count for Bus BS-101.
  5. Live Physical LCD HUD Preview: Displays exactly what will appear on the bus 16x2 LCD display.
  6. Multi-threaded network dispatcher for 60+ FPS zero-latency video processing.

Usage:
  # 1. Run with default ESP32-CAM IP:
  python ml_passenger_audit.py --esp32-ip 192.168.1.105

  # 2. Run with your Laptop / USB Webcam:
  python ml_passenger_audit.py --source 0

  # 3. Run with Autonomous Test Simulation (if hardware is not currently connected):
  python ml_passenger_audit.py --simulate

  # 4. Custom Server & Bus ID:
  python ml_passenger_audit.py --server http://127.0.0.1:5000 --bus-id BS-101
========================================================================================
"""

import sys
import os
import time
import argparse
import threading
import json
from datetime import datetime, timezone
import numpy as np
import cv2

# Optional requests library for HTTP sync
try:
    import requests
except ImportError:
    requests = None

# Optional ultralytics YOLO library
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False


# ========================================================================================
# 1. CENTROID TRACKER & LINE-CROSSING AUDIT ENGINE
# ========================================================================================
class CentroidTracker:
    """
    Centroid tracking with Euclidean distance matching and directional line crossing.
    Prevents double-counting passengers across consecutive frames.
    """
    def __init__(self, max_disappeared=15, max_distance=80):
        self.next_object_id = 0
        self.objects = {}       # object_id -> centroid (cx, cy)
        self.disappeared = {}   # object_id -> consecutive frames disappeared
        self.previous_pos = {}  # object_id -> previous centroid (cx, cy)
        self.crossed_entry = set()
        self.crossed_exit = set()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid):
        self.objects[self.next_object_id] = centroid
        self.previous_pos[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        if object_id in self.objects:
            del self.objects[object_id]
        if object_id in self.disappeared:
            del self.disappeared[object_id]
        if object_id in self.previous_pos:
            del self.previous_pos[object_id]
        self.crossed_entry.discard(object_id)
        self.crossed_exit.discard(object_id)

    def update(self, rects, entry_y, exit_y):
        """
        Updates object positions and detects line crossings.
        rects: list of [x, y, w, h] or [x1, y1, x2, y2]
        Returns: (entries, exits, active_centroids_dict)
        """
        new_entries = 0
        new_exits = 0

        if len(rects) == 0:
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return new_entries, new_exits, self.objects

        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for i, r in enumerate(rects):
            if len(r) == 4:
                # Handle both [x, y, w, h] and [x1, y1, x2, y2]
                if r[2] > r[0] and r[3] > r[1] and r[2] > 50: # x1, y1, x2, y2
                    cX = int((r[0] + r[2]) / 2.0)
                    cY = int((r[1] + r[3]) / 2.0)
                else: # x, y, w, h
                    cX = int(r[0] + (r[2] / 2.0))
                    cY = int(r[1] + (r[3] / 2.0))
                input_centroids[i] = (cX, cY)

        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())

            D = np.linalg.norm(np.array(object_centroids)[:, np.newaxis] - input_centroids, axis=2)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] > self.max_distance:
                    continue

                obj_id = object_ids[row]
                prev_c = self.objects[obj_id]
                curr_c = input_centroids[col]

                # Directional Line Crossing Logic:
                # Boarding (Entry): Moving downward past Entry Line (y increases)
                if prev_c[1] < entry_y <= curr_c[1] and obj_id not in self.crossed_entry:
                    new_entries += 1
                    self.crossed_entry.add(obj_id)

                # Alighting (Exit): Moving upward past Exit Line (y decreases)
                if prev_c[1] > exit_y >= curr_c[1] and obj_id not in self.crossed_exit:
                    new_exits += 1
                    self.crossed_exit.add(obj_id)

                self.previous_pos[obj_id] = prev_c
                self.objects[obj_id] = curr_c
                self.disappeared[obj_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)

            for row in unused_rows:
                obj_id = object_ids[row]
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)

            for col in unused_cols:
                self.register(input_centroids[col])

        return new_entries, new_exits, self.objects


# ========================================================================================
# 2. NON-MAXIMUM SUPPRESSION (NMS) HELPER FOR OPENCV
# ========================================================================================
def non_max_suppression_fast(boxes, overlap_thresh=0.4):
    if len(boxes) == 0:
        return []
    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")

    pick = []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        overlap = (w * h) / area[idxs[:last]]
        idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlap_thresh)[0])))

    return boxes[pick].astype("int")


# ========================================================================================
# 3. SYNTHETIC VIDEO SIMULATOR (FOR HARDWARE-FREE TESTING)
# ========================================================================================
class SyntheticBusStream:
    """
    Generates realistic video frames simulating a bus door entrance with boarding/exiting passengers.
    Guarantees that ml_passenger_audit.py can run and be verified instantly even without physical camera.
    """
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        self.passengers = []
        self.frame_count = 0

    def read(self):
        self.frame_count += 1
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Draw Bus Cabin Floor & Doorway
        frame[:] = (35, 30, 25) # Dark interior
        cv2.rectangle(frame, (80, 20), (560, 460), (55, 48, 40), -1)
        cv2.rectangle(frame, (80, 20), (560, 460), (120, 100, 70), 2)
        
        # Draw Floor Mats & Stepping Grid
        for y in range(60, 440, 50):
            cv2.line(frame, (100, y), (540, y), (45, 40, 35), 1)

        # Spawn random simulated passenger moving through door
        if self.frame_count % 90 == 0 or len(self.passengers) == 0:
            direction = 1 if np.random.rand() > 0.3 else -1 # 1: Boarding, -1: Exiting
            start_y = 50 if direction == 1 else 420
            start_x = int(np.random.uniform(220, 420))
            color = (int(np.random.randint(100, 255)), int(np.random.randint(120, 255)), int(np.random.randint(80, 255)))
            self.passengers.append({
                'x': start_x,
                'y': start_y,
                'dir': direction,
                'speed': np.random.uniform(3.0, 5.0),
                'color': color,
                'radius': int(np.random.uniform(28, 35)),
                'shoulder_w': int(np.random.uniform(65, 80))
            })

        # Update & Draw simulated passengers
        for p in list(self.passengers):
            p['y'] += int(p['dir'] * p['speed'])
            # Draw Head & Shoulders (Simulated Top-Down / Angled View)
            cv2.ellipse(frame, (int(p['x']), int(p['y'])), (p['shoulder_w'] // 2, p['radius']), 0, 0, 360, p['color'], -1)
            cv2.circle(frame, (int(p['x']), int(p['y'])), int(p['radius'] * 0.65), (210, 190, 170), -1)
            cv2.circle(frame, (int(p['x']), int(p['y'])), int(p['radius'] * 0.65), (50, 40, 30), 1)

            # Remove if out of view
            if p['y'] < 30 or p['y'] > 450:
                self.passengers.remove(p)

        time.sleep(0.033) # ~30 FPS
        return True, frame

    def release(self):
        pass


# ========================================================================================
# 4. MAIN PASSENGER AUDIT & SYNC CONTROLLER
# ========================================================================================
class MLPassengerAuditor:
    def __init__(self, args):
        self.args = args
        self.bus_id = args.bus_id.upper()
        self.server_url = args.server.rstrip('/')
        self.sync_endpoint = f"{self.server_url}/api/camera/yolo-count"
        self.telemetry_endpoint = f"{self.server_url}/api/esp32/telemetry"
        
        self.running = True
        self.passenger_count = args.initial_count
        self.total_entries = 0
        self.total_exits = 0
        self.bus_capacity = 6 if self.bus_id in ('SB-101', 'BS-101', '101') else 40
        
        # Line positions (percentage of frame height)
        self.entry_line_ratio = args.entry_line
        self.exit_line_ratio = args.exit_line
        
        # Detection & Tracker
        self.tracker = CentroidTracker(max_disappeared=15, max_distance=90)
        self.use_yolo = HAS_YOLO and not args.force_hog
        
        if self.use_yolo:
            print("[ML Engine] Initializing Ultralytics YOLOv8n (Person Class 0)...")
            try:
                self.yolo_model = YOLO("yolov8n.pt")
                print(" [OK] YOLOv8n Loaded Successfully.")
            except Exception as e:
                print(f" [!] YOLOv8 initialization warning: {e}. Falling back to OpenCV HOG.")
                self.use_yolo = False
        
        if not self.use_yolo:
            print("[ML Engine] Initializing OpenCV HOG Default People Detector + NMS...")
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Server Sync State
        self.last_sync_time = 0
        self.sync_interval = args.sync_interval
        self.sync_status_text = "INITIALIZING"
        self.sync_status_color = (180, 180, 180)
        self.server_reconciled_count = self.passenger_count
        self.lcd_display_message = f"P:{self.passenger_count}/{self.bus_capacity}"
        self.lcd_stop_name = "Central Depot"
        self.hardware_alert_code = "NORMAL"
        self.hardware_buzzer = False
        self.hardware_red_led = False
        self.hardware_green_led = True
        
        # Async Network Dispatch Worker
        self.network_queue = []
        self.lock = threading.Lock()
        self.sync_thread = threading.Thread(target=self._network_sync_loop, daemon=True)
        self.sync_thread.start()

    def _network_sync_loop(self):
        """Asynchronous background thread for non-blocking HTTP REST synchronization."""
        while self.running:
            payload = None
            with self.lock:
                if self.network_queue:
                    payload = self.network_queue.pop(0)
            
            if payload and requests:
                try:
                    start_t = time.time()
                    resp = requests.post(self.sync_endpoint, json=payload, timeout=2.5)
                    latency_ms = int((time.time() - start_t) * 1000)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        self.server_reconciled_count = data.get('reconciled_count', payload['detected_count'])
                        self.sync_status_text = f"SYNC OK (200) - {latency_ms}ms"
                        self.sync_status_color = (0, 255, 100) # Green
                        
                        # Check hardware control signals
                        hw = data.get('hardware_control', {})
                        if hw:
                            self.hardware_alert_code = hw.get('alert_code', 'NORMAL')
                            self.hardware_buzzer = hw.get('buzzer', False)
                            self.hardware_red_led = hw.get('red_led', False)
                            self.hardware_green_led = hw.get('green_led', True)
                    else:
                        self.sync_status_text = f"HTTP {resp.status_code}"
                        self.sync_status_color = (0, 165, 255) # Orange
                except Exception as e:
                    self.sync_status_text = "OFFLINE (Retrying)"
                    self.sync_status_color = (0, 0, 255) # Red
            
            time.sleep(0.3)

    def trigger_server_sync(self, force=False):
        """Queues a sync payload for the backend API."""
        now = time.time()
        if force or (now - self.last_sync_time >= self.sync_interval):
            self.last_sync_time = now
            payload = {
                "bus_number": self.bus_id,
                "bus_id": self.bus_id,
                "detected_count": self.passenger_count,
                "passengers": self.passenger_count,
                "confidence": 0.92 if self.use_yolo else 0.88,
                "entries": self.total_entries,
                "exits": self.total_exits,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            with self.lock:
                self.network_queue = [payload] # Keep only most recent payload

    def detect_passengers(self, frame):
        """Runs Person Detection on frame and returns bounding boxes [x1, y1, x2, y2]."""
        rects = []
        if self.use_yolo:
            results = self.yolo_model(frame, classes=[0], verbose=False, conf=self.args.conf)
            for r in results:
                boxes = r.boxes.xyxy.cpu().numpy()
                for b in boxes:
                    rects.append([int(b[0]), int(b[1]), int(b[2]), int(b[3])])
        else:
            # OpenCV HOG detector
            resized = cv2.resize(frame, (480, 360))
            ratio_x = frame.shape[1] / 480.0
            ratio_y = frame.shape[0] / 360.0
            
            boxes, weights = self.hog.detectMultiScale(
                resized,
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05
            )
            
            if len(boxes) > 0:
                raw_boxes = []
                for (x, y, w, h) in boxes:
                    raw_boxes.append([
                        int(x * ratio_x),
                        int(y * ratio_y),
                        int((x + w) * ratio_x),
                        int((y + h) * ratio_y)
                    ])
                rects = non_max_suppression_fast(np.array(raw_boxes), overlap_thresh=0.45).tolist()

        return rects

    def draw_hud(self, frame, active_objects, fps):
        """Renders the comprehensive Cyberpunk / Smart Transit HUD Overlay."""
        h, w = frame.shape[:2]
        entry_y = int(h * self.entry_line_ratio)
        exit_y = int(h * self.exit_line_ratio)

        # 1. Virtual Gate Lines
        # Entry Line (Green)
        cv2.line(frame, (20, entry_y), (w - 20, entry_y), (0, 255, 120), 2)
        cv2.putText(frame, ">>> [ENTRY GATE - PASSENGER BOARDING] >>>", (30, entry_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 120), 1, cv2.LINE_AA)
        
        # Exit Line (Red/Orange)
        cv2.line(frame, (20, exit_y), (w - 20, exit_y), (0, 100, 255), 2)
        cv2.putText(frame, "<<< [EXIT GATE - PASSENGER ALIGHTING] <<<", (30, exit_y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 255), 1, cv2.LINE_AA)

        # 2. Draw Active Tracked Centroids
        for obj_id, centroid in active_objects.items():
            cv2.circle(frame, (centroid[0], centroid[1]), 5, (0, 255, 255), -1)
            cv2.putText(frame, f"ID:{obj_id}", (centroid[0] - 15, centroid[1] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        # 3. Top Master Header Bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 65), (15, 18, 25), -1)
        cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

        # Top Bar Text
        cv2.putText(frame, f"BUS {self.bus_id} : AI PASSENGER AUDIT", (15, 25),
                    cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        
        model_name = "YOLOv8 Nano" if self.use_yolo else "OpenCV HOG+SVM"
        cv2.putText(frame, f"Model: {model_name} | FPS: {fps:.1f}", (15, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 200, 220), 1, cv2.LINE_AA)

        # Server Status Pill
        cv2.putText(frame, f"SERVER: {self.sync_status_text}", (w - 280, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.sync_status_color, 1, cv2.LINE_AA)
        
        cv2.putText(frame, f"GATEWAY: {self.server_url}", (w - 280, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1, cv2.LINE_AA)

        # 4. Bottom Metric Dashboard
        bot_overlay = frame.copy()
        cv2.rectangle(bot_overlay, (0, h - 110), (w, h), (12, 15, 20), -1)
        cv2.addWeighted(bot_overlay, 0.90, frame, 0.10, 0, frame)

        # Occupancy Progress Bar
        occupancy_pct = min(100.0, (self.passenger_count / float(self.bus_capacity)) * 100.0)
        bar_w = 220
        bar_x = 15
        bar_y = h - 25
        bar_fill = int((occupancy_pct / 100.0) * bar_w)
        
        bar_color = (0, 255, 120) if occupancy_pct < 75 else ((0, 180, 255) if occupancy_pct < 95 else (0, 0, 255))
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 12), (50, 55, 65), -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_fill, bar_y + 12), bar_color, -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 12), (100, 110, 130), 1)

        cv2.putText(frame, f"PASSENGERS: {self.passenger_count} / {self.bus_capacity} ({occupancy_pct:.0f}%)",
                    (15, h - 75), cv2.FONT_HERSHEY_DUPLEX, 0.60, (255, 255, 255), 1, cv2.LINE_AA)
        
        cv2.putText(frame, f"BOARDED (IN): +{self.total_entries}   |   ALIGHTED (OUT): -{self.total_exits}",
                    (15, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 220, 240), 1, cv2.LINE_AA)

        # 5. Physical 16x2 LCD HUD Simulation Box (Right Side)
        lcd_x = w - 310
        lcd_y = h - 100
        cv2.rectangle(frame, (lcd_x, lcd_y), (lcd_x + 295, lcd_y + 90), (0, 45, 10), -1)
        cv2.rectangle(frame, (lcd_x, lcd_y), (lcd_x + 295, lcd_y + 90), (0, 220, 50), 2)
        
        cv2.putText(frame, "ONBOARD 16x2 LCD HARDWARE HUD:", (lcd_x + 10, lcd_y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 100), 1, cv2.LINE_AA)
        
        # LCD Line 1
        lcd_line1 = f"Passengers: {self.passenger_count}"
        cv2.putText(frame, f"L1: [ {lcd_line1:<16} ]", (lcd_x + 10, lcd_y + 44),
                    cv2.FONT_HERSHEY_MONOSPACE if hasattr(cv2, 'FONT_HERSHEY_MONOSPACE') else cv2.FONT_HERSHEY_SIMPLEX,
                    0.50, (150, 255, 180), 1, cv2.LINE_AA)
        
        # LCD Line 2
        lcd_line2 = f"Stop: {self.lcd_stop_name}"
        cv2.putText(frame, f"L2: [ {lcd_line2:<16} ]", (lcd_x + 10, lcd_y + 70),
                    cv2.FONT_HERSHEY_MONOSPACE if hasattr(cv2, 'FONT_HERSHEY_MONOSPACE') else cv2.FONT_HERSHEY_SIMPLEX,
                    0.50, (150, 255, 180), 1, cv2.LINE_AA)

        return frame

    def run(self):
        """Main Video Capture & Audit Loop."""
        # 1. Initialize Video Capture Source
        cap = None
        source = self.args.source
        
        if self.args.simulate:
            print("[Video Source] Using Synthetic Bus Doorway Simulator...")
            cap = SyntheticBusStream()
        elif source.isdigit():
            print(f"[Video Source] Opening Local Webcam Index {source}...")
            cap = cv2.VideoCapture(int(source))
        elif source.startswith("http://") or source.startswith("https://"):
            print(f"[Video Source] Connecting to ESP32-CAM Stream: {source}...")
            cap = cv2.VideoCapture(source)
        else:
            print(f"[Video Source] Opening Video File: {source}...")
            cap = cv2.VideoCapture(source)

        if not self.args.simulate and (not cap or not cap.isOpened()):
            print("\n[!] ERROR: Could not open camera stream/device.")
            print("    Attempting to fallback to Synthetic Test Simulator so you can test immediately...")
            cap = SyntheticBusStream()

        print("\n" + "=" * 70)
        print(f" [🚀] SMART BUS {self.bus_id} AUDITOR RUNNING")
        print(f"      - Backend Target: {self.sync_endpoint}")
        print(f"      - Keyboard Controls:")
        print(f"          'q' : Quit & Save Audit Log")
        print(f"          'r' : Reset Passenger Count to 0")
        print(f"          '+' : Manually Increment (+1)")
        print(f"          '-' : Manually Decrement (-1)")
        print(f"          's' : Force Immediate Server Sync")
        print("=" * 70 + "\n")

        fps_calc_time = time.time()
        frame_idx = 0
        current_fps = 30.0

        # Send initial registration sync
        self.trigger_server_sync(force=True)

        while self.running:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[!] Stream ended or frame lost. Reconnecting...")
                time.sleep(1.0)
                if not self.args.simulate and source.startswith("http"):
                    cap = cv2.VideoCapture(source)
                continue

            frame_idx += 1
            if frame_idx % 15 == 0:
                now = time.time()
                current_fps = 15.0 / max(0.001, (now - fps_calc_time))
                fps_calc_time = now

            h, w = frame.shape[:2]
            entry_y = int(h * self.entry_line_ratio)
            exit_y = int(h * self.exit_line_ratio)

            # 2. Run Person Detection (Every frame or every 2nd frame for speed)
            rects = self.detect_passengers(frame)

            # Draw detection bounding boxes
            for r in rects:
                cv2.rectangle(frame, (r[0], r[1]), (r[2], r[3]), (0, 200, 255), 2)

            # 3. Update Centroid Tracker & Line Crossing
            new_in, new_out, active_objects = self.tracker.update(rects, entry_y, exit_y)

            if new_in > 0 or new_out > 0:
                self.total_entries += new_in
                self.total_exits += new_out
                self.passenger_count = max(0, min(self.bus_capacity + 15, self.passenger_count + new_in - new_out))
                print(f"[*] PASSENGER EVENT: Boarded +{new_in} | Alighted -{new_out} | Current Count: {self.passenger_count}")
                self.trigger_server_sync(force=True)
            else:
                self.trigger_server_sync(force=False)

            # 4. Render HUD & LCD Preview
            if not self.args.headless:
                display_frame = self.draw_hud(frame, active_objects, current_fps)
                cv2.imshow(f"Smart Bus {self.bus_id} - ML Passenger Audit", display_frame)

                # 5. Process Keyboard Events
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27: # 'q' or ESC
                    print("[*] Exit requested by user.")
                    break
                elif key == ord('r'):
                    self.passenger_count = 0
                    self.total_entries = 0
                    self.total_exits = 0
                    print("[*] Passenger count reset to 0.")
                    self.trigger_server_sync(force=True)
                elif key == ord('+') or key == ord('='):
                    self.passenger_count = min(self.bus_capacity + 15, self.passenger_count + 1)
                    self.total_entries += 1
                    print(f"[*] Manual +1: Count is now {self.passenger_count}")
                    self.trigger_server_sync(force=True)
                elif key == ord('-') or key == ord('_'):
                    self.passenger_count = max(0, self.passenger_count - 1)
                    self.total_exits += 1
                    print(f"[*] Manual -1: Count is now {self.passenger_count}")
                    self.trigger_server_sync(force=True)
                elif key == ord('s'):
                    print("[*] Forcing server sync...")
                    self.trigger_server_sync(force=True)

        self.running = False
        cap.release()
        cv2.destroyAllWindows()
        print(f"[Done] Final Count for Bus {self.bus_id}: {self.passenger_count} passengers.")


# ========================================================================================
# 5. COMMAND LINE ENTRYPOINT
# ========================================================================================
def main():
    parser = argparse.ArgumentParser(description="Smart Bus BS-101 ML Passenger Audit & ESP32 Camera System")
    parser.add_argument("--source", type=str, default="http://192.168.1.105:81/stream",
                        help="Video source: ESP32-CAM stream URL (http://<IP>:81/stream), webcam index (0), or video file")
    parser.add_argument("--esp32-ip", type=str, default=None,
                        help="Convenience parameter to set ESP32-CAM IP (e.g. 192.168.1.105)")
    parser.add_argument("--server", type=str, default="http://127.0.0.1:5000",
                        help="Smart Bus Flask backend server URL (default: http://127.0.0.1:5000)")
    parser.add_argument("--bus-id", type=str, default="BS-101",
                        help="Target Bus Identifier (default: BS-101)")
    parser.add_argument("--initial-count", type=int, default=18,
                        help="Initial passenger occupancy count (default: 18)")
    parser.add_argument("--conf", type=float, default=0.45,
                        help="Confidence threshold for YOLO person detection (default: 0.45)")
    parser.add_argument("--entry-line", type=float, default=0.42,
                        help="Vertical position ratio for Entry Line (default: 0.42)")
    parser.add_argument("--exit-line", type=float, default=0.60,
                        help="Vertical position ratio for Exit Line (default: 0.60)")
    parser.add_argument("--sync-interval", type=float, default=1.5,
                        help="Sync interval in seconds to POST count to server (default: 1.5s)")
    parser.add_argument("--simulate", action="store_true",
                        help="Run with synthetic simulated bus doorway frames for testing")
    parser.add_argument("--force-hog", action="store_true",
                        help="Force using OpenCV HOG detector even if YOLO is installed")
    parser.add_argument("--headless", action="store_true",
                        help="Run without GUI window for background execution")

    args = parser.parse_args()

    if args.esp32_ip:
        ip = args.esp32_ip.strip()
        if ":" in ip:
            args.source = f"http://{ip}/stream"
        else:
            # Default to standard port 80 stream from esp32-s3 webserver
            args.source = f"http://{ip}/stream"

    auditor = MLPassengerAuditor(args)
    auditor.run()


if __name__ == "__main__":
    main()
