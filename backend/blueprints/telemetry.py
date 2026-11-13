from flask import Blueprint, request, jsonify
from backend.services.telemetry_service import telemetry_service

telemetry_bp = Blueprint('telemetry_bp', __name__)

@telemetry_bp.route('/telemetry', methods=['POST'])
@telemetry_bp.route('/esp32/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Primary endpoint for ESP32-S3 Hardware (Bus SB-101) and Simulation telemetry ingestion.
    Supports real GPS, dual IR passenger counting, RFID, and hardware actuator commands.
    """
    data = request.get_json() or {}
    bus_no = data.get('bus_number') or data.get('bus_name', 'SB-101')
    stop_name = data.get('stop') or data.get('current_stop', 'Unknown')
    p_count = data.get('passengers', 0)
    eta_val = data.get('eta', '--')
    ard_bytes = data.get('arduino_bytes')
    active_pin = data.get('active_pin')
    pin_sig = data.get('pin_signal')
    sig_text = " [Wire: 🟢 HIGH]" if pin_sig == 1 else " [Wire: 🔴 LOW]" if pin_sig == 0 else ""
    pin_diag = f" | [ESP32 on GPIO {active_pin}{sig_text}]" if active_pin is not None else ""
    rx_prev = data.get('rx_preview', '')
    prev_str = f" | [Rx Preview: '{rx_prev}']" if rx_prev else ""
    ard_info = f" | Mega Bytes RX: {ard_bytes}{pin_diag}{prev_str}" if ard_bytes is not None else " | (⚠️ ESP32 has NOT been uploaded with new sketch yet!)"
    print(f"\n>>> [TELEMETRY INGESTION] From {request.remote_addr} -> Bus: {bus_no} | Stop: {stop_name} | Passengers: {p_count} | ETA: {eta_val}m{ard_info}", flush=True)
    result = telemetry_service.process_telemetry_payload(data)
    
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code

