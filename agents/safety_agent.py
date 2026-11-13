from backend.services.safety_service import safety_service, SafetyService
from backend.services.camera_service import camera_service

class SafetyAgent:
    """
    Intelligent Safety Agent responsible for:
    - Real-time overcrowding detection & capacity management (Dual IR & YOLOv8n CV).
    - Driver safety monitoring & prolonged eye closure / drowsiness detection.
    - Emergency SOS alert processing & priority dispatch.
    - Dynamic safety scoring for fleet vehicles and drivers.
    - Actuator control signals for ESP32-S3 and Arduino UNO (Buzzer, Red/Green LEDs, LCD Display).
    """

    def __init__(self, speed_limit_kmh=65.0):
        self.service = safety_service
        self.camera = camera_service

    def evaluate_bus_safety(self, bus, telemetry_data=None, is_drowsy=False):
        return self.service.evaluate_safety(bus, telemetry_data, is_drowsy=is_drowsy)

    def trigger_sos(self, bus_id, lat=None, lng=None):
        return self.service.trigger_sos(bus_id, lat, lng)

    def resolve_emergency(self, bus_id, admin_user='Admin'):
        return self.service.resolve_emergency(bus_id, admin_user)

    def process_driver_drowsiness(self, bus_id, ear_score=0.18, mar_score=0.15, consecutive_frames=20, confidence=0.92):
        return self.camera.evaluate_driver_drowsiness(bus_id, ear_score=ear_score, mar_score=mar_score, consecutive_closed_frames=consecutive_frames, confidence=confidence)

safety_agent = SafetyAgent()

