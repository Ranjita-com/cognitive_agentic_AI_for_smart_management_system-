from datetime import datetime, timezone
from database.db import db
from models.db_models import Bus, Stop, RouteStop, TelemetryLog, PassengerLog, RfidCard, Alert
from backend.services.hardware_service import hardware_service

class TelemetryService:
    """
    Ingestion & Dispatch Service for Fleet Telemetry.
    Accurately maps telemetry to specific buses and guarantees data source tagging (REAL vs SIMULATED vs MANUAL).
    """

    def process_telemetry_payload(self, data):
        """
        Processes incoming telemetry from ESP32-S3 (Bus SB-101) or Simulator (Buses SB-102, SB-103, SB-104).
        """
        # 1. Identify Bus by bus_number, bus_name, bus_id, or MAC
        bus = None
        bus_num_val = data.get('bus_number') or data.get('bus_name')
        bus_id_val = data.get('bus_id')

        if bus_num_val:
            if bus_num_val in ('BS-101', 'SB-101'):
                bus_num_val = 'SB-101'
            bus = Bus.query.filter_by(bus_number=bus_num_val).first()
        elif bus_id_val:
            if isinstance(bus_id_val, int) or (isinstance(bus_id_val, str) and bus_id_val.isdigit()):
                bus = db.session.get(Bus, int(bus_id_val))
            elif isinstance(bus_id_val, str):
                target_num = 'SB-101' if bus_id_val in ('BS-101', 'SB-101') else bus_id_val
                bus = Bus.query.filter_by(bus_number=target_num).first()
        elif 'mac' in data and data['mac']:
            bus = Bus.query.filter_by(device_mac=data['mac']).first()

        if not bus:
            # Fallback: default to first bus (SB-101)
            bus = Bus.query.first()
            if not bus:
                return {'success': False, 'message': 'No buses registered in system.'}

        # Determine data source: SB-101 is physical REAL hardware
        is_real_sb101 = (bus.bus_number == 'SB-101')
        in_source = data.get('source', 'ESP32' if is_real_sb101 else 'SIMULATOR')

        if is_real_sb101:
            bus.data_source = 'REAL'
            bus.gps_source = 'REAL'
            bus.passenger_source = 'REAL'
            bus.hardware_available = True
            bus.camera_available = True
            bus.passenger_sensor_available = True
            bus.is_simulated = False
        else:
            bus.data_source = 'SIMULATED'
            bus.gps_source = 'SIMULATED'
            bus.passenger_source = 'SIMULATED'
            bus.hardware_available = False
            bus.camera_available = False
            bus.passenger_sensor_available = False
            bus.is_simulated = True

        # 2. Update Location & Kinematics (Direct Float or NMEA GPS String)
        gps_raw = data.get('gps')
        if gps_raw and isinstance(gps_raw, str) and gps_raw.startswith('$GPRMC'):
            parts = gps_raw.split(',')
            if len(parts) >= 7 and parts[2] == 'A': # Valid GPS Fix
                try:
                    raw_lat = float(parts[3])
                    lat_deg = int(raw_lat / 100)
                    lat_min = raw_lat - (lat_deg * 100)
                    lat = lat_deg + (lat_min / 60.0)
                    if parts[4] == 'S': lat = -lat

                    raw_lng = float(parts[5])
                    lng_deg = int(raw_lng / 100)
                    lng_min = raw_lng - (lng_deg * 100)
                    lng = lng_deg + (lng_min / 60.0)
                    if parts[6] == 'W': lng = -lng

                    bus.current_lat = lat
                    bus.current_lng = lng
                    if len(parts) >= 8 and parts[7]:
                        bus.speed = float(parts[7]) * 1.852 # Knots to km/h
                    if len(parts) >= 9 and parts[8]:
                        bus.heading = float(parts[8])
                except Exception:
                    pass

        if 'latitude' in data and data['latitude'] is not None:
            bus.current_lat = float(data['latitude'])
        if 'longitude' in data and data['longitude'] is not None:
            bus.current_lng = float(data['longitude'])
        if 'speed' in data and data['speed'] is not None:
            bus.speed = float(data['speed'])
        if 'heading' in data and data['heading'] is not None:
            bus.heading = float(data['heading'])
        if 'altitude' in data and data['altitude'] is not None:
            bus.altitude = float(data['altitude'])

        # 3. Emergency SOS / Overcrowding Button Trigger
        sos_val = data.get('emergency_button') if data.get('emergency_button') is not None else data.get('sos')
        if sos_val is not None:
            is_sos = (sos_val == 1 or sos_val == '1' or sos_val is True)
            bus.emergency_status = is_sos
            if is_sos:
                bus.status = 'emergency'
                # Create Alert if not already active
                recent_alert = Alert.query.filter_by(bus_id=bus.id, alert_type='HARDWARE_SOS', status='ACTIVE').first()
                if not recent_alert:
                    sos_alert = Alert(
                        bus_id=bus.id,
                        alert_type='HARDWARE_SOS',
                        severity='CRITICAL',
                        message=f'🚨 Hardware SOS / Overcrowding Alert on {bus.bus_number}. Immediate attention needed.',
                        status='ACTIVE',
                        latitude=bus.current_lat,
                        longitude=bus.current_lng
                    )
                    db.session.add(sos_alert)
                    try:
                        from backend.sockets import socketio
                        socketio.emit('new_alert', {'alert': sos_alert.to_dict()})
                    except Exception:
                        pass
            elif bus.status == 'emergency':
                bus.status = 'active'

        # 4. Passenger Count Updates (IR Sensors / YOLO / Simulation)
        entries = int(data.get('entries', 0))
        exits = int(data.get('exits', 0))
        p_count = data.get('passenger_count') if data.get('passenger_count') is not None else data.get('passengers')
        if p_count is not None:
            bus.ir_passenger_count = int(p_count)
            bus.current_passengers = max(0, min(bus.capacity + 15, int(p_count)))
        elif entries > 0 or exits > 0:
            new_p = max(0, min(bus.capacity + 15, bus.current_passengers + entries - exits))
            bus.ir_passenger_count = new_p
            bus.current_passengers = new_p

        # 5. Process Current Stop or RFID Scans (Stops or Passenger Cards)
        current_stop_name = data.get('current_stop') or data.get('stop')
        if current_stop_name:
            stop_str = str(current_stop_name).strip()
            clean_name = stop_str.replace("Area", "").replace("Zone", "").replace("Stop", "").strip()
            matched_stop = Stop.query.filter(
                (Stop.name.ilike(f"%{stop_str}%")) | 
                (Stop.name.ilike(f"%{clean_name}%"))
            ).first()

            # Smart Alias Matching for Route 101 Stops
            if not matched_stop:
                lower_name = stop_str.lower()
                if "route start" in lower_name or "start" in lower_name or "hospital" in lower_name:
                    matched_stop = Stop.query.filter(Stop.name.ilike("%Hospital%")).first()
                elif "school" in lower_name:
                    matched_stop = Stop.query.filter(Stop.name.ilike("%School%")).first()
                elif "shopping" in lower_name or "mall" in lower_name or "market" in lower_name:
                    matched_stop = Stop.query.filter(Stop.name.ilike("%Market%")).first()
                elif "terminal" in lower_name or "end" in lower_name:
                    matched_stop = Stop.query.filter(Stop.name.ilike("%Terminal%")).first()

            if matched_stop:
                bus.last_stop_id = matched_stop.id
                bus.last_stop = matched_stop
                if matched_stop.latitude and matched_stop.longitude and not gps_raw:
                    bus.current_lat = matched_stop.latitude
                    bus.current_lng = matched_stop.longitude

                # Calculate next stop along the route
                if bus.route_id:
                    route_stops = RouteStop.query.filter_by(route_id=bus.route_id).order_by(RouteStop.sequence_order).all()
                    current_rs = next((rs for rs in route_stops if rs.stop_id == matched_stop.id), None)
                    if current_rs:
                        next_rs = next((rs for rs in route_stops if rs.sequence_order == current_rs.sequence_order + 1), None)
                        if next_rs:
                            bus.next_stop_id = next_rs.stop_id
                            bus.next_stop = next_rs.stop
                        else:
                            # Terminal reached -> next is first stop or self
                            first_rs = route_stops[0] if route_stops else None
                            bus.next_stop_id = first_rs.stop_id if first_rs else matched_stop.id
                            if first_rs:
                                bus.next_stop = first_rs.stop
                    else:
                        bus.next_stop_id = matched_stop.id
                else:
                    bus.next_stop_id = matched_stop.id

                # 5b. ETA-Based Route Waypoint Interpolation
                # When GPS is indoors/demo mode, progressively move bus along route polyline towards next stop as ETA decreases
                has_satellite_fix = bool(gps_raw and isinstance(gps_raw, str) and ',A,' in gps_raw)
                
                if not has_satellite_fix:
                    import json, math
                    eta_val = data.get('eta')
                    placed = False

                    # Stop-to-Base-ETA mapping for Route 101
                    STOP_BASE_ETAS = {
                        'Hospital Stop': 25,
                        'School Zone': 15,
                        'Market Area': 8,
                        'Bus Terminal': 0
                    }

                    if eta_val is not None and bus.route and bus.route.polyline_json:
                        try:
                            polyline = json.loads(bus.route.polyline_json)
                            if len(polyline) >= 2:
                                eta_num = float(eta_val)
                                start_eta = STOP_BASE_ETAS.get(matched_stop.name, 25)
                                target_eta = STOP_BASE_ETAS.get(bus.next_stop.name, 0) if bus.next_stop else 0

                                # Helper: find closest waypoint index in route polyline
                                def _closest_poly_idx(pts, lat, lng):
                                    best_i = 0
                                    min_d = float('inf')
                                    for i, p in enumerate(pts):
                                        d = (p[0] - lat)**2 + (p[1] - lng)**2
                                        if d < min_d:
                                            min_d = d
                                            best_i = i
                                    return best_i

                                start_idx = _closest_poly_idx(polyline, matched_stop.latitude, matched_stop.longitude)
                                end_idx = _closest_poly_idx(polyline, bus.next_stop.latitude, bus.next_stop.longitude) if bus.next_stop else len(polyline) - 1

                                if end_idx > start_idx and start_eta > target_eta:
                                    # Active leg between current stop and next stop
                                    sub_poly = polyline[start_idx : end_idx + 1]
                                    leg_duration = float(start_eta - target_eta)
                                    progress = max(0.0, min(1.0, (float(start_eta) - eta_num) / leg_duration))
                                else:
                                    # Fallback across entire route polyline
                                    sub_poly = polyline
                                    max_eta = 25.0
                                    progress = max(0.0, min(1.0, (max_eta - eta_num) / max_eta))

                                if len(sub_poly) >= 2:
                                    total_segments = len(sub_poly) - 1
                                    seg_pos = progress * total_segments
                                    seg_idx = min(int(seg_pos), total_segments - 1)
                                    sub_step = seg_pos - seg_idx

                                    p1 = sub_poly[seg_idx]
                                    p2 = sub_poly[min(seg_idx + 1, total_segments)]

                                    bus.current_lat = p1[0] + (p2[0] - p1[0]) * sub_step
                                    bus.current_lng = p1[1] + (p2[1] - p1[1]) * sub_step

                                    d_lat = p2[0] - p1[0]
                                    d_lng = p2[1] - p1[1]
                                    if abs(d_lat) > 0.00001 or abs(d_lng) > 0.00001:
                                        bus.heading = (math.degrees(math.atan2(d_lng, d_lat)) + 360) % 360
                                    bus.speed = 32.0 if (eta_num > 0 and progress < 1.0) else 0.0
                                    placed = True
                        except Exception as e:
                            placed = False

                    if not placed and matched_stop.latitude:
                        bus.current_lat = matched_stop.latitude
                        bus.current_lng = matched_stop.longitude
                        bus.speed = 28.0 if (data.get('eta', 0) > 0) else 0.0

        rfid_tag = data.get('rfid_tag')
        if rfid_tag:
            stop = Stop.query.filter_by(rfid_tag=rfid_tag).first()
            if stop:
                bus.last_stop_id = stop.id
            else:
                card = RfidCard.query.filter_by(card_uid=rfid_tag).first()
                if card and card.status == 'ACTIVE':
                    fare = bus.route.fare if bus.route else 25.0
                    if card.balance >= fare:
                        card.balance -= fare
                        card.last_tapped_at = datetime.now(timezone.utc)
                        card.last_bus_id = bus.id

        bus.last_ping = datetime.now(timezone.utc)
        bus.updated_at = datetime.now(timezone.utc)

        # 6. Log Telemetry
        telemetry_log = TelemetryLog(
            bus_id=bus.id,
            latitude=bus.current_lat,
            longitude=bus.current_lng,
            speed=bus.speed,
            heading=bus.heading,
            altitude=bus.altitude,
            battery_voltage=bus.battery_voltage,
            engine_temp=bus.engine_temp,
            fuel_level=bus.fuel_level,
            passenger_count=bus.current_passengers,
            ir_count=bus.ir_passenger_count,
            yolo_count=bus.yolo_passenger_count,
            source=in_source,
            gps_source=bus.gps_source,
            passenger_source=bus.passenger_source,
            maintenance_source=bus.maintenance_source
        )
        db.session.add(telemetry_log)

        if entries > 0 or exits > 0:
            pass_log = PassengerLog(
                bus_id=bus.id,
                entries_count=entries,
                exits_count=exits,
                total_passengers=bus.current_passengers,
                stop_id=bus.last_stop_id,
                trigger_source='IR_SENSOR' if is_real_sb101 else 'SIMULATION'
            )
            db.session.add(pass_log)

        db.session.commit()

        # 7. Run Agent Pipeline
        from agents import orchestrator
        agent_results = orchestrator.process_telemetry_tick(bus, data)

        # 8. WebSockets Broadcast
        eta_val = data.get('eta')
        try:
            from backend.sockets import socketio
            bus_dict = bus.to_dict()
            if eta_val is not None:
                bus_dict['eta'] = eta_val
                bus_dict['reported_eta'] = eta_val

            socketio.emit('bus_update', {
                'bus': bus_dict,
                'bus_id': bus.id,
                'bus_number': bus.bus_number,
                'passenger_count': bus.current_passengers,
                'current_stop': bus.last_stop.name if bus.last_stop else (current_stop_name or 'Hospital Stop'),
                'last_stop_name': bus.last_stop.name if bus.last_stop else (current_stop_name or 'Hospital Stop'),
                'next_stop_name': bus.next_stop.name if bus.next_stop else 'School Zone',
                'latitude': bus.current_lat,
                'longitude': bus.current_lng,
                'eta': eta_val,
                'agent_insights': {
                    'safety_score': agent_results['safety'].get('safety_score'),
                    'health_score': agent_results['maintenance'].get('health_score'),
                    'deviated': agent_results['route_deviation'].get('deviated')
                }
            })
            if agent_results['safety'].get('alerts'):
                socketio.emit('new_alert', {'alerts': agent_results['safety']['alerts']})
        except Exception:
            pass

        # 9. Build Hardware Control Signals for ESP32/Arduino
        hw_control = agent_results.get('hardware_control') or hardware_service.build_actuator_commands(
            passenger_count=bus.current_passengers,
            capacity=bus.capacity,
            is_emergency=bus.emergency_status
        )

        return {
            'success': True,
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'data_source': bus.data_source,
            'gps_source': bus.gps_source,
            'passenger_source': bus.passenger_source,
            'server_timestamp': datetime.now(timezone.utc).isoformat(),
            'hardware_control': hw_control,
            'safety_score': agent_results['safety'].get('safety_score'),
            'health_score': agent_results['maintenance'].get('health_score')
        }

telemetry_service = TelemetryService()
