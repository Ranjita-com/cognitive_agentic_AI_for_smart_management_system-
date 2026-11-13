import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, Response
from database.db import db
from models.db_models import Bus, Driver, Route, TelemetryLog, PassengerLog, Alert
from agents.passenger_agent import passenger_agent
from backend.services.camera_service import camera_service

bus_bp = Blueprint('bus_bp', __name__)

@bus_bp.route('/buses', methods=['GET'])
def get_buses():
    route_id = request.args.get('route_id', type=int)
    status = request.args.get('status')
    
    query = Bus.query
    if route_id:
        query = query.filter_by(route_id=route_id)
    if status:
        query = query.filter_by(status=status)
        
    buses = query.all()
    results = []
    for b in buses:
        bus_dict = b.to_dict()
        bus_dict['hardware_type'] = 'PHYSICAL_ESP32_S3' if b.hardware_available or b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED'
        eta_info = passenger_agent.calculate_eta(b.id)
        bus_dict['dynamic_eta_mins'] = eta_info.get('eta_minutes', 5)
        results.append(bus_dict)
        
    return jsonify({'success': True, 'count': len(results), 'buses': results})

@bus_bp.route('/buses/<int:bus_id>', methods=['GET'])
def get_bus_details(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    bus_dict = bus.to_dict()
    bus_dict['hardware_type'] = 'PHYSICAL_ESP32_S3' if bus.hardware_available or bus.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED'
    
    recent_telemetry = [t.to_dict() for t in bus.telemetry_logs[-15:]]
    recent_passenger_logs = [p.to_dict() for p in PassengerLog.query.filter_by(bus_id=bus.id).order_by(PassengerLog.timestamp.desc()).limit(10).all()]
    eta_info = passenger_agent.calculate_eta(bus.id)
    
    bus_dict['telemetry_history'] = recent_telemetry
    bus_dict['passenger_history'] = recent_passenger_logs
    bus_dict['eta_details'] = eta_info
    
    return jsonify({'success': True, 'bus': bus_dict})

@bus_bp.route('/buses', methods=['POST'])
def create_bus():
    data = request.get_json() or {}
    bus_number = data.get('bus_number', '').strip().upper()
    license_plate = data.get('license_plate', '').strip().upper()
    
    if not bus_number:
        return jsonify({'success': False, 'message': 'Bus number is required.'}), 400
        
    if not license_plate:
        license_plate = f"KA-01-F-{bus_number.replace('-', '')[-4:]}"
        
    if Bus.query.filter_by(bus_number=bus_number).first():
        return jsonify({'success': False, 'message': 'Bus number already exists.'}), 409
        
    is_sb101 = (bus_number == 'SB-101')
    route_val = data.get('route_id')
    driver_val = data.get('driver_id')
    
    # Resolve route_id (could be ID int or route_number string)
    route_id = None
    if route_val:
        if isinstance(route_val, int) or (isinstance(route_val, str) and str(route_val).isdigit()):
            route_id = int(route_val)
        else:
            clean_r = str(route_val).strip().lstrip('R').lstrip('r').strip()
            r = Route.query.filter(
                (Route.route_number == str(route_val)) | 
                (Route.route_number == clean_r) | 
                (Route.name.ilike(f"%{clean_r}%"))
            ).first()
            if r:
                route_id = r.id

    # Resolve driver_id (could be ID int or license/name string)
    driver_id = None
    if driver_val:
        if isinstance(driver_val, int) or (isinstance(driver_val, str) and str(driver_val).isdigit()):
            driver_id = int(driver_val)
        else:
            d = Driver.query.filter(
                (Driver.license_number == str(driver_val)) | 
                (Driver.name.ilike(f"%{driver_val}%"))
            ).first()
            if d:
                driver_id = d.id

    # Starting coordinates from route if available
    start_lat = 12.9716
    start_lng = 77.5946
    if route_id:
        try:
            route = Route.query.get(int(route_id))
            if route and route.polyline_json:
                poly = json.loads(route.polyline_json)
                if poly and len(poly) > 0:
                    start_lat = poly[0][0]
                    start_lng = poly[0][1]
        except Exception:
            pass

    bus = Bus(
        bus_number=bus_number,
        license_plate=license_plate,
        model=data.get('model', 'Volvo 9700 Smart Edition'),
        capacity=int(data.get('capacity', 40)),
        route_id=route_id,
        driver_id=driver_id,
        status=data.get('status', 'active' if route_id else 'standby'),
        current_lat=start_lat,
        current_lng=start_lng,
        speed=30.0 if route_id else 0.0,
        is_simulated=False if is_sb101 else data.get('is_simulated', True),
        hardware_available=is_sb101,
        camera_available=is_sb101,
        gps_available=True,
        passenger_sensor_available=is_sb101,
        data_source='REAL' if is_sb101 else 'SIMULATED',
        gps_source='REAL' if is_sb101 else 'SIMULATED',
        passenger_source='REAL' if is_sb101 else 'SIMULATED',
        maintenance_source='MANUAL'
    )
    db.session.add(bus)
    db.session.commit()
    
    # Broadcast to live map and passenger apps
    try:
        from backend.sockets import socketio
        socketio.emit('bus_update', {'bus': bus.to_dict()})
    except Exception:
        pass

    return jsonify({'success': True, 'message': 'Bus created and deployed successfully.', 'bus': bus.to_dict()}), 201

@bus_bp.route('/buses/swap', methods=['POST'])
def swap_buses():
    data = request.get_json() or {}
    source_val = data.get('source_bus_id') or data.get('bus1_id') or data.get('bus_id_1') or data.get('bus_id')
    target_val = data.get('target_bus_id') or data.get('bus2_id') or data.get('bus_id_2') or data.get('replacement_bus_id')
    new_route_val = data.get('new_route_id') or data.get('route_id')
    reason = data.get('reason', 'Admin Operational Fleet Swap')

    new_route_id = None
    if new_route_val:
        if isinstance(new_route_val, int) or (isinstance(new_route_val, str) and str(new_route_val).isdigit()):
            new_route_id = int(new_route_val)
        else:
            clean_r = str(new_route_val).strip().lstrip('R').lstrip('r').strip()
            r = Route.query.filter((Route.route_number == str(new_route_val)) | (Route.route_number == clean_r) | (Route.name.ilike(f"%{clean_r}%"))).first()
            if r:
                new_route_id = r.id

    if not source_val:
        return jsonify({'success': False, 'message': 'Source bus ID is required.'}), 400

    # Resolve source bus
    source_bus = None
    if isinstance(source_val, int) or (isinstance(source_val, str) and str(source_val).isdigit()):
        source_bus = Bus.query.get(int(source_val))
    if not source_bus and isinstance(source_val, str):
        source_bus = Bus.query.filter_by(bus_number=source_val.strip().upper()).first()

    if not source_bus:
        return jsonify({'success': False, 'message': f'Bus {source_val} not found.'}), 404

    target_bus = None
    if target_val:
        if isinstance(target_val, int) or (isinstance(target_val, str) and str(target_val).isdigit()):
            target_bus = Bus.query.get(int(target_val))
        if not target_bus and isinstance(target_val, str):
            target_bus = Bus.query.filter_by(bus_number=target_val.strip().upper()).first()
        if target_bus and target_bus.id == source_bus.id:
            target_bus = None


    if target_bus:
        orig_route_id = source_bus.route_id
        orig_status = source_bus.status
        orig_lat = source_bus.current_lat
        orig_lng = source_bus.current_lng
        orig_last_stop = source_bus.last_stop_id
        orig_next_stop = source_bus.next_stop_id

        target_route_id = target_bus.route_id
        target_status = target_bus.status
        target_lat = target_bus.current_lat
        target_lng = target_bus.current_lng
        target_last_stop = target_bus.last_stop_id
        target_next_stop = target_bus.next_stop_id

        # Swap assignments
        source_bus.route_id = target_route_id if (new_route_id is None) else int(new_route_id)
        source_bus.status = 'active' if source_bus.route_id else target_status
        if target_lat and target_lng:
            source_bus.current_lat = target_lat
            source_bus.current_lng = target_lng
        source_bus.last_stop_id = target_last_stop
        source_bus.next_stop_id = target_next_stop

        target_bus.route_id = orig_route_id
        target_bus.status = 'active' if target_bus.route_id else 'standby'
        if orig_lat and orig_lng:
            target_bus.current_lat = orig_lat
            target_bus.current_lng = orig_lng
        target_bus.last_stop_id = orig_last_stop
        target_bus.next_stop_id = orig_next_stop

        db.session.commit()

        # Update simulator engine states
        try:
            from simulation.bus_simulator import simulator_engine
            simulator_engine.bus_states.pop(source_bus.id, None)
            simulator_engine.bus_states.pop(target_bus.id, None)
        except Exception:
            pass

        # Create audit alert
        route_name = source_bus.route.name if source_bus.route else 'Standby'
        swap_alert = Alert(
            bus_id=source_bus.id,
            alert_type='FLEET_SWAP',
            severity='INFO',
            message=f"🔄 Fleet Swap: {source_bus.bus_number} swapped assignments with {target_bus.bus_number}. Reason: {reason}.",
            status='RESOLVED',
            latitude=source_bus.current_lat,
            longitude=source_bus.current_lng
        )
        db.session.add(swap_alert)
        db.session.commit()

        # Socket broadcast
        try:
            from backend.sockets import socketio
            socketio.emit('bus_reallocated', {
                'degraded_bus': target_bus.to_dict(),
                'replacement_bus': source_bus.to_dict(),
                'route_number': source_bus.route.route_number if source_bus.route else '',
                'route_name': route_name,
                'reason': reason,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            socketio.emit('bus_update', {'bus': source_bus.to_dict()})
            socketio.emit('bus_update', {'bus': target_bus.to_dict()})
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': f'Successfully swapped {source_bus.bus_number} and {target_bus.bus_number}.',
            'source_bus': source_bus.to_dict(),
            'target_bus': target_bus.to_dict()
        })
    elif new_route_id:
        new_route = Route.query.get(int(new_route_id))
        if not new_route:
            return jsonify({'success': False, 'message': 'Target route not found.'}), 404

        source_bus.route_id = new_route.id
        source_bus.status = 'active'
        if new_route.polyline_json:
            try:
                poly = json.loads(new_route.polyline_json)
                if poly and len(poly) > 0:
                    source_bus.current_lat = poly[0][0]
                    source_bus.current_lng = poly[0][1]
            except Exception:
                pass
        
        db.session.commit()

        # Update simulator engine states
        try:
            from simulation.bus_simulator import simulator_engine
            simulator_engine.bus_states.pop(source_bus.id, None)
        except Exception:
            pass

        try:
            from backend.sockets import socketio
            socketio.emit('bus_update', {'bus': source_bus.to_dict()})
            socketio.emit('bus_reallocated', {
                'replacement_bus': source_bus.to_dict(),
                'route_number': new_route.route_number,
                'route_name': new_route.name,
                'reason': reason,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': f'{source_bus.bus_number} successfully reassigned to Route {new_route.route_number} ({new_route.name}).',
            'source_bus': source_bus.to_dict()
        })
    else:
        return jsonify({'success': False, 'message': 'Either target_bus_id or new_route_id must be provided.'}), 400

@bus_bp.route('/buses/<int:bus_id>', methods=['PUT'])
def update_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    data = request.get_json() or {}
    
    if 'model' in data: bus.model = data['model']
    if 'capacity' in data: bus.capacity = int(data['capacity'])
    if 'route_id' in data: bus.route_id = data['route_id']
    if 'driver_id' in data: bus.driver_id = data['driver_id']
    if 'status' in data: bus.status = data['status']
    if 'current_passengers' in data: bus.current_passengers = int(data['current_passengers'])
    if 'passenger_reconciliation_strategy' in data:
        bus.passenger_reconciliation_strategy = data['passenger_reconciliation_strategy']
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Bus updated successfully.', 'bus': bus.to_dict()})

@bus_bp.route('/buses/<int:bus_id>', methods=['DELETE'])
def delete_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    try:
        from simulation.bus_simulator import simulator_engine
        simulator_engine.bus_states.pop(bus.id, None)
    except Exception:
        pass

    from models.db_models import MaintenanceRecord, CameraEvent, DriverSafetyEvent, MaintenanceAssessment, Feedback, FleetRecommendation
    TelemetryLog.query.filter_by(bus_id=bus.id).delete()
    PassengerLog.query.filter_by(bus_id=bus.id).delete()
    Alert.query.filter_by(bus_id=bus.id).delete()
    MaintenanceRecord.query.filter_by(bus_id=bus.id).delete()
    CameraEvent.query.filter_by(bus_id=bus.id).delete()
    DriverSafetyEvent.query.filter_by(bus_id=bus.id).delete()
    MaintenanceAssessment.query.filter_by(bus_id=bus.id).delete()
    Feedback.query.filter_by(bus_id=bus.id).delete()
    FleetRecommendation.query.filter_by(bus_id=bus.id).delete()

    db.session.delete(bus)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Bus {bus.bus_number} deleted.'})

@bus_bp.route('/buses/<int:bus_id>/camera', methods=['GET'])
def get_camera_frame(bus_id):
    """
    Returns live camera SVG feed for Bus SB-101 (OV3660 camera onboard feed).
    For other buses without physical camera, returns a clear NOT AVAILABLE graphic.
    """
    bus = Bus.query.get_or_404(bus_id)
    
    if not bus.camera_available and bus.bus_number != 'SB-101':
        # Bus has no physical camera
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
          <rect width="640" height="360" fill="#0f172a"/>
          <circle cx="320" cy="150" r="40" fill="#1e293b" stroke="#475569" stroke-width="2"/>
          <line x1="290" y1="120" x2="350" y2="180" stroke="#ef4444" stroke-width="3"/>
          <text x="320" y="230" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#94a3b8" text-anchor="middle">Camera: NOT AVAILABLE</text>
          <text x="320" y="260" font-family="Arial, sans-serif" font-size="13" fill="#64748b" text-anchor="middle">Bus {bus.bus_number} is software simulated. Physical OV3660 camera only installed on Bus SB-101.</text>
        </svg>"""
        return Response(svg, mimetype='image/svg+xml')

    # SB-101 physical camera feed representation
    occupancy = bus.occupancy_rate
    status_color = '#10b981' if occupancy < 80 else ('#f59e0b' if occupancy < 100 else '#ef4444')
    cam_status = camera_service.get_camera_status('SB-101')
    yolo_count = bus.yolo_passenger_count
    ir_count = bus.ir_passenger_count
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#090d16"/>
          <stop offset="100%" stop-color="#111827"/>
        </linearGradient>
      </defs>
      <rect width="640" height="360" fill="url(#bg)"/>
      <!-- Grid Reticle -->
      <line x1="40" y1="40" x2="80" y2="40" stroke="#38bdf8" stroke-width="2"/>
      <line x1="40" y1="40" x2="40" y2="80" stroke="#38bdf8" stroke-width="2"/>
      <line x1="600" y1="40" x2="560" y2="40" stroke="#38bdf8" stroke-width="2"/>
      <line x1="600" y1="40" x2="600" y2="80" stroke="#38bdf8" stroke-width="2"/>
      <line x1="40" y1="320" x2="80" y2="320" stroke="#38bdf8" stroke-width="2"/>
      <line x1="40" y1="320" x2="40" y2="280" stroke="#38bdf8" stroke-width="2"/>
      <line x1="600" y1="320" x2="560" y2="320" stroke="#38bdf8" stroke-width="2"/>
      <line x1="600" y1="320" x2="600" y2="280" stroke="#38bdf8" stroke-width="2"/>
      
      <!-- Virtual Cabin Layout & Bounding Boxes -->
      <ellipse cx="320" cy="180" rx="140" ry="80" fill="#1e293b" opacity="0.6"/>
      <circle cx="320" cy="140" r="28" fill="#334155"/>
      <rect x="270" y="105" width="100" height="90" fill="none" stroke="#10b981" stroke-width="2" stroke-dasharray="4,4"/>
      <text x="275" y="100" font-family="monospace" font-size="10" fill="#10b981">DRIVER [EAR: 0.31]</text>
      
      <!-- Top Status Overlay -->
      <rect x="30" y="20" width="580" height="35" rx="6" fill="#000000" opacity="0.8"/>
      <circle cx="50" cy="37" r="6" fill="#10b981"/>
      <text x="65" y="42" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#ffffff">CAMERA: ONLINE</text>
      <text x="210" y="42" font-family="monospace" font-size="12" fill="#38bdf8">ESP32-S3 OV3660 [BUS: {bus.bus_number}]</text>
      <text x="490" y="42" font-family="monospace" font-size="12" fill="#94a3b8">YOLOv8n: {yolo_count} P</text>

      <!-- Bottom HUD -->
      <rect x="30" y="295" width="580" height="45" rx="6" fill="#000000" opacity="0.85"/>
      <text x="50" y="322" font-family="Arial, sans-serif" font-size="12" fill="#cbd5e1">IR COUNT: {ir_count} | YOLO COUNT: {yolo_count} | FINAL OCCUPANCY: {bus.current_passengers}/{bus.capacity}</text>
      <rect x="420" y="312" width="90" height="10" rx="3" fill="#334155"/>
      <rect x="420" y="312" width="{min(90, int(90 * occupancy / 100))}" height="10" rx="3" fill="{status_color}"/>
      <text x="520" y="322" font-family="monospace" font-size="11" fill="{status_color}">{occupancy:.0f}%</text>
    </svg>"""
    return Response(svg, mimetype='image/svg+xml')

@bus_bp.route('/camera/status', methods=['GET'])
def get_camera_status():
    bus_number = request.args.get('bus_number', 'SB-101')
    status = camera_service.get_camera_status(bus_number)
    return jsonify({'success': True, 'camera': status})

@bus_bp.route('/camera/yolo-count', methods=['POST'])
def update_yolo_count():
    data = request.get_json() or {}
    bus_number = data.get('bus_number') or data.get('bus_id') or 'BS-101'
    detected_count = int(data.get('detected_count') if data.get('detected_count') is not None else data.get('passengers', 0))
    confidence = float(data.get('confidence', 0.90))
    
    result = camera_service.process_yolo_detection(bus_number, detected_count, confidence)
    return jsonify(result)

@bus_bp.route('/camera/drowsiness-event', methods=['POST'])
def report_drowsiness_event():
    data = request.get_json() or {}
    bus_number = data.get('bus_number', 'SB-101')
    ear = float(data.get('ear', 0.18))
    mar = float(data.get('mar', 0.15))
    confidence = float(data.get('confidence', 0.94))
    
    result = camera_service.report_driver_drowsiness(bus_number, ear=ear, mar=mar, confidence=confidence)
    return jsonify(result)

@bus_bp.route('/camera/stream', methods=['GET'])
@bus_bp.route('/camera/live-stream', methods=['GET'])
@bus_bp.route('/buses/<int:bus_id>/live-stream', methods=['GET'])
def get_live_yolo_stream(bus_id=1):
    """
    Live real-time MJPEG video stream rendered directly in the webpage
    showing YOLOv8 person bounding boxes, tracking centroids, entry/exit gates,
    and the 16x2 LCD HUD preview.
    """
    return Response(
        camera_service.generate_annotated_stream(bus_identifier="BS-101"),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@bus_bp.route('/camera/stream-config', methods=['GET', 'POST'])
def handle_stream_config():
    if request.method == 'POST':
        data = request.get_json() or {}
        source_type = data.get('source_type', 'simulate') # esp32, webcam, simulate
        stream_url = data.get('stream_url')
        res = camera_service.set_stream_config(source_type=source_type, stream_url=stream_url)
        return jsonify(res)
    else:
        return jsonify({
            'source_type': getattr(camera_service, 'stream_source_type', 'simulate'),
            'stream_url': getattr(camera_service, 'stream_url', 'http://10.246.81.168/stream')
        })

@bus_bp.route('/fleet/reset', methods=['POST'])
@bus_bp.route('/simulation/reset-data', methods=['POST'])
def reset_fleet_data():
    """
    Resets the entire fleet, bus route assignments, and simulator states back to original defaults:
    - SB-101 (Physical IoT): Line 101, Driver Michael Vance, 6 seats capacity, 0 passengers, active, pristine health.
    - SB-102 (Simulated): Line 202, Driver David Miller, 40 seats, active.
    - SB-103 (Simulated): Line 303, Driver Sarah Connor, 42 seats, active.
    - SB-104 (Auxiliary): Central Depot Standby (no route, no driver), 45 seats.
    - SB-105 (Auxiliary): Central Depot Standby (no route, no driver), 42 seats.
    - Deletes any dynamically generated test buses (SB-TEST-*).
    - Resolves all active emergency alerts.
    - Deletes fleet reallocation recommendations (undoes swaps).
    - Resets simulation engine bus waypoints so buses start from beginning of routes.
    - Broadcasts live WebSocket event to instantly update admin dashboard, maps, and lists.
    """
    try:
        from models.db_models import Bus, Route, Driver, Stop, Alert, FleetRecommendation
        
        # 1. Resolve standard routes
        route101 = Route.query.filter_by(route_number='101').first()
        route202 = Route.query.filter_by(route_number='202').first()
        route303 = Route.query.filter_by(route_number='303').first()
        
        # 2. Resolve drivers
        drivers = Driver.query.order_by(Driver.id).all()
        d_vance = drivers[0] if len(drivers) > 0 else None
        d_miller = drivers[1] if len(drivers) > 1 else None
        d_connor = drivers[2] if len(drivers) > 2 else None
        
        # 3. Resolve key stops
        st_101 = Stop.query.filter_by(code='ST-101').first()
        st_102 = Stop.query.filter_by(code='ST-102').first()
        st_201 = Stop.query.filter_by(code='ST-201').first()
        st_202 = Stop.query.filter_by(code='ST-202').first()
        st_301 = Stop.query.filter_by(code='ST-301').first()
        st_302 = Stop.query.filter_by(code='ST-302').first()

        # 4. Remove any temporary test buses
        Bus.query.filter(Bus.bus_number.like('SB-TEST%')).delete(synchronize_session=False)

        # 5. Reset Bus SB-101 (Real Physical IoT - Volvo 9700 Smart Edition)
        bus101 = Bus.query.filter_by(bus_number='SB-101').first()
        if bus101:
            bus101.route_id = route101.id if route101 else None
            bus101.driver_id = d_vance.id if d_vance else None
            bus101.capacity = 6
            bus101.current_passengers = 0
            bus101.ir_passenger_count = 0
            bus101.yolo_passenger_count = 0
            bus101.status = 'active'
            bus101.emergency_status = False
            bus101.speed = 35.0
            bus101.heading = 45.0
            bus101.current_lat = 12.9740
            bus101.current_lng = 77.5970
            bus101.last_stop_id = st_101.id if st_101 else None
            bus101.next_stop_id = st_102.id if st_102 else None
            bus101.battery_voltage = 12.6
            bus101.engine_temp = 84.5
            bus101.fuel_level = 78.0
            bus101.tire_pressure = 32.0
            bus101.brake_health = 92.0
            bus101.engine_health = 94.0
            bus101.transmission_health = 95.0
            bus101.maintenance_notes = 'Nominal physical depot test bus.'
            bus101.maintenance_priority = 'NORMAL'
            bus101.safety_score = 98.0
            bus101.health_score = 94.0
            bus101.is_simulated = False
            bus101.hardware_available = True
            bus101.camera_available = True
            bus101.passenger_sensor_available = True
            bus101.data_source = 'REAL'
            bus101.gps_source = 'REAL'
            bus101.passenger_source = 'REAL'

        # 6. Reset Bus SB-102 (Simulated on Route 202 Blue Airport Direct)
        bus102 = Bus.query.filter_by(bus_number='SB-102').first()
        if bus102:
            bus102.route_id = route202.id if route202 else None
            bus102.driver_id = d_miller.id if d_miller else None
            bus102.capacity = 40
            bus102.current_passengers = 18
            bus102.status = 'active'
            bus102.emergency_status = False
            bus102.speed = 42.0
            bus102.heading = 52.0
            bus102.current_lat = 13.0450
            bus102.current_lng = 77.6500
            bus102.last_stop_id = st_201.id if st_201 else None
            bus102.next_stop_id = st_202.id if st_202 else None
            bus102.maintenance_priority = 'NORMAL'
            bus102.safety_score = 95.0
            bus102.health_score = 92.0
            bus102.is_simulated = True

        # 7. Reset Bus SB-103 (Simulated on Route 303 Red City Circular)
        bus103 = Bus.query.filter_by(bus_number='SB-103').first()
        if bus103:
            bus103.route_id = route303.id if route303 else None
            bus103.driver_id = d_connor.id if d_connor else None
            bus103.capacity = 42
            bus103.current_passengers = 12
            bus103.status = 'active'
            bus103.emergency_status = False
            bus103.speed = 35.0
            bus103.heading = 90.0
            bus103.current_lat = 12.9600
            bus103.current_lng = 77.5800
            bus103.last_stop_id = st_301.id if st_301 else None
            bus103.next_stop_id = st_302.id if st_302 else None
            bus103.maintenance_priority = 'NORMAL'
            bus103.safety_score = 98.0
            bus103.health_score = 96.0
            bus103.is_simulated = True

        # 8. Reset Bus SB-104 (Standby in Depot)
        bus104 = Bus.query.filter_by(bus_number='SB-104').first()
        if bus104:
            bus104.route_id = None
            bus104.driver_id = None
            bus104.capacity = 45
            bus104.current_passengers = 0
            bus104.status = 'standby'
            bus104.emergency_status = False
            bus104.speed = 0.0
            bus104.current_lat = 13.0450
            bus104.current_lng = 77.6500
            bus104.maintenance_priority = 'NORMAL'
            bus104.safety_score = 98.0
            bus104.health_score = 96.0
            bus104.is_simulated = True

        # 9. Reset Bus SB-105 (Standby in Depot)
        bus105 = Bus.query.filter_by(bus_number='SB-105').first()
        if bus105:
            bus105.route_id = None
            bus105.driver_id = None
            bus105.capacity = 42
            bus105.current_passengers = 0
            bus105.status = 'standby'
            bus105.emergency_status = False
            bus105.speed = 0.0
            bus105.current_lat = 12.9716
            bus105.current_lng = 77.5946
            bus105.maintenance_priority = 'NORMAL'
            bus105.safety_score = 99.0
            bus105.health_score = 98.0
            bus105.is_simulated = True

        # 10. Clear active emergency alerts & recommendations
        Alert.query.filter_by(status='ACTIVE').update({'status': 'RESOLVED', 'resolved_at': datetime.now(timezone.utc)})
        FleetRecommendation.query.delete()

        db.session.commit()

        # 11. Reset Simulator Waypoint states
        try:
            from simulation.bus_simulator import simulator_engine
            simulator_engine.bus_states.clear()
        except Exception:
            pass

        # 12. Broadcast to all connected clients
        try:
            from backend.sockets import socketio
            for b in Bus.query.all():
                socketio.emit('bus_update', {'bus': b.to_dict()})
            socketio.emit('fleet_reset', {'message': 'Fleet restored to default initial state.'})
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': 'Fleet data successfully reset to initial defaults (SB-101 on Line 101 with 6 seats, swaps undone, alerts cleared).'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to reset fleet data: {str(e)}'}), 500




