import json
from datetime import datetime, timezone
from database.db import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='passenger') # admin, driver, passenger
    phone = db.Column(db.String(20), nullable=True)
    rfid_card_id = db.Column(db.String(50), unique=True, nullable=True)
    wallet_balance = db.Column(db.Float, default=100.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'phone': self.phone,
            'rfid_card_id': self.rfid_card_id,
            'wallet_balance': round(self.wallet_balance, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Driver(db.Model):
    __tablename__ = 'drivers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    experience_years = db.Column(db.Integer, default=3)
    rating = db.Column(db.Float, default=4.8)
    status = db.Column(db.String(20), default='on_duty') # on_duty, off_duty, break
    total_trips = db.Column(db.Integer, default=120)
    safety_violations = db.Column(db.Integer, default=0)
    avatar = db.Column(db.String(255), default='https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    buses = db.relationship('Bus', backref='driver', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'license_number': self.license_number,
            'phone': self.phone,
            'email': self.email,
            'experience_years': self.experience_years,
            'rating': self.rating,
            'status': self.status,
            'total_trips': self.total_trips,
            'safety_violations': self.safety_violations,
            'avatar': self.avatar if self.avatar and not self.avatar.startswith('https://images.unsplash') else '/assets/images/driver_cockpit.jpg'
        }


class Route(db.Model):
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    origin = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    distance_km = db.Column(db.Float, default=12.5)
    estimated_duration_mins = db.Column(db.Integer, default=35)
    fare = db.Column(db.Float, default=25.0)
    color = db.Column(db.String(20), default='#3b82f6')
    polyline_json = db.Column(db.Text, default='[]')
    is_active = db.Column(db.Boolean, default=True)

    buses = db.relationship('Bus', backref='route', lazy=True)
    route_stops = db.relationship('RouteStop', backref='route', cascade='all, delete-orphan', lazy=True, order_by='RouteStop.sequence_order')

    def to_dict(self, include_stops=False):
        data = {
            'id': self.id,
            'route_number': self.route_number,
            'name': self.name,
            'origin': self.origin,
            'destination': self.destination,
            'distance_km': self.distance_km,
            'estimated_duration_mins': self.estimated_duration_mins,
            'fare': self.fare,
            'color': self.color,
            'polyline': json.loads(self.polyline_json) if self.polyline_json else [],
            'is_active': self.is_active
        }
        if include_stops:
            data['stops'] = [rs.to_dict() for rs in self.route_stops]
        return data


class Stop(db.Model):
    __tablename__ = 'stops'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    rfid_tag = db.Column(db.String(50), unique=True, nullable=True)
    address = db.Column(db.String(200), default='')
    amenities_json = db.Column(db.Text, default='["Shelter", "Digital Display", "Seating"]')

    route_stops = db.relationship('RouteStop', backref='stop', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'rfid_tag': self.rfid_tag,
            'address': self.address,
            'amenities': json.loads(self.amenities_json) if self.amenities_json else []
        }


class RouteStop(db.Model):
    __tablename__ = 'route_stops'
    
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False)
    stop_duration_secs = db.Column(db.Integer, default=30)
    distance_from_start_km = db.Column(db.Float, default=0.0)
    arrival_time_offset_mins = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'route_id': self.route_id,
            'stop_id': self.stop_id,
            'stop_name': self.stop.name if self.stop else '',
            'stop_code': self.stop.code if self.stop else '',
            'latitude': self.stop.latitude if self.stop else 0.0,
            'longitude': self.stop.longitude if self.stop else 0.0,
            'rfid_tag': self.stop.rfid_tag if self.stop else '',
            'sequence_order': self.sequence_order,
            'distance_from_start_km': self.distance_from_start_km,
            'arrival_time_offset_mins': self.arrival_time_offset_mins
        }


class Bus(db.Model):
    __tablename__ = 'buses'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    model = db.Column(db.String(50), default='Volvo 9700 Smart Edition')
    capacity = db.Column(db.Integer, default=40)
    current_passengers = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active') # active, idle, standby, maintenance, emergency
    
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=True)
    
    # Telemetry
    current_lat = db.Column(db.Float, default=12.9716)
    current_lng = db.Column(db.Float, default=77.5946)
    speed = db.Column(db.Float, default=0.0)
    heading = db.Column(db.Float, default=0.0)
    altitude = db.Column(db.Float, default=920.0)
    
    last_stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=True)
    next_stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=True)
    
    # Safety & Diagnostics
    emergency_status = db.Column(db.Boolean, default=False)
    battery_voltage = db.Column(db.Float, default=12.6) # Manual/Admin entered or nominal (No physical ADC on bus)
    engine_temp = db.Column(db.Float, default=85.0) # Celsius Manual/Admin entered
    fuel_level = db.Column(db.Float, default=75.0) # Percentage
    tire_pressure = db.Column(db.Float, default=32.0) # PSI Manual/Admin entered
    brake_health = db.Column(db.Float, default=88.0) # % Manual/Admin entered
    engine_health = db.Column(db.Float, default=92.0) # % Manual/Admin entered
    transmission_health = db.Column(db.Float, default=94.0) # % Manual/Admin entered
    maintenance_notes = db.Column(db.String(255), default='Nominal maintenance parameters.')
    maintenance_priority = db.Column(db.String(20), default='NORMAL') # NORMAL, MONITOR, SERVICE_REQUIRED, CRITICAL
    safety_score = db.Column(db.Float, default=95.0)
    health_score = db.Column(db.Float, default=92.0)
    
    # Real Hardware vs Software/Simulated Identification
    hardware_available = db.Column(db.Boolean, default=False) # True ONLY for physical SB-101
    camera_available = db.Column(db.Boolean, default=False)   # True ONLY for physical SB-101 OV3660
    gps_available = db.Column(db.Boolean, default=True)
    passenger_sensor_available = db.Column(db.Boolean, default=False) # True ONLY for physical SB-101 IR sensors
    
    # Data Sources (Explicitly labeled)
    data_source = db.Column(db.String(20), default='SIMULATED') # REAL, SIMULATED
    gps_source = db.Column(db.String(20), default='SIMULATED') # REAL, SIMULATED
    passenger_source = db.Column(db.String(20), default='SIMULATED') # REAL, SIMULATED
    maintenance_source = db.Column(db.String(20), default='MANUAL') # MANUAL, SIMULATED
    
    # Passenger Counting Layers (Physical IR vs YOLOv8n Computer Vision)
    ir_passenger_count = db.Column(db.Integer, default=0)
    yolo_passenger_count = db.Column(db.Integer, default=0)
    passenger_reconciliation_strategy = db.Column(db.String(20), default='IR_PRIMARY') # IR_PRIMARY, YOLO_PRIMARY, HYBRID
    
    is_simulated = db.Column(db.Boolean, default=True)
    device_mac = db.Column(db.String(50), default='ESP32_S3_A1:B2:C3')
    last_ping = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    last_stop = db.relationship('Stop', foreign_keys=[last_stop_id])
    next_stop = db.relationship('Stop', foreign_keys=[next_stop_id])
    telemetry_logs = db.relationship('TelemetryLog', backref='bus', lazy=True, order_by='desc(TelemetryLog.timestamp)')
    alerts = db.relationship('Alert', backref='bus', lazy=True, order_by='desc(Alert.created_at)')
    camera_events = db.relationship('CameraEvent', backref='bus', lazy=True, order_by='desc(CameraEvent.timestamp)')
    driver_safety_events = db.relationship('DriverSafetyEvent', backref='bus', lazy=True, order_by='desc(DriverSafetyEvent.timestamp)')
    maintenance_assessments = db.relationship('MaintenanceAssessment', backref='bus', lazy=True, order_by='desc(MaintenanceAssessment.timestamp)')

    @property
    def occupancy_rate(self):
        if self.capacity <= 0:
            return 0.0
        return min(100.0, (self.current_passengers / self.capacity) * 100.0)

    @property
    def available_seats(self):
        return max(0, self.capacity - self.current_passengers)

    def to_dict(self):
        return {
            'id': self.id,
            'bus_number': self.bus_number,
            'license_plate': self.license_plate,
            'model': self.model,
            'capacity': self.capacity,
            'current_passengers': self.current_passengers,
            'available_seats': self.available_seats,
            'occupancy_rate': round(self.occupancy_rate, 1),
            'status': self.status,
            'route_id': self.route_id,
            'route_number': self.route.route_number if self.route else None,
            'route_name': self.route.name if self.route else None,
            'route_color': self.route.color if self.route else '#10b981',
            'driver_id': self.driver_id,
            'driver_name': self.driver.name if self.driver else 'Unassigned',
            'driver_phone': self.driver.phone if self.driver else '',
            'fare': self.route.fare if self.route else 30.0,
            'ticket_price': self.route.fare if self.route else 30.0,
            'current_lat': self.current_lat,
            'current_lng': self.current_lng,
            'speed': round(self.speed, 1),
            'heading': round(self.heading, 1),
            'altitude': round(self.altitude, 1),
            'last_stop_id': self.last_stop_id,
            'last_stop_name': self.last_stop.name if self.last_stop else None,
            'next_stop_id': self.next_stop_id,
            'next_stop_name': self.next_stop.name if self.next_stop else None,
            'emergency_status': self.emergency_status,
            'battery_voltage': round(self.battery_voltage, 2),
            'engine_temp': round(self.engine_temp, 1),
            'fuel_level': round(self.fuel_level, 1),
            'tire_pressure': round(self.tire_pressure, 1),
            'brake_health': round(self.brake_health, 1),
            'engine_health': round(self.engine_health, 1),
            'transmission_health': round(self.transmission_health, 1),
            'maintenance_notes': self.maintenance_notes,
            'maintenance_priority': self.maintenance_priority,
            'safety_score': round(self.safety_score, 1),
            'health_score': round(self.health_score, 1),
            'hardware_available': self.hardware_available,
            'camera_available': self.camera_available,
            'gps_available': self.gps_available,
            'passenger_sensor_available': self.passenger_sensor_available,
            'data_source': self.data_source,
            'gps_source': self.gps_source,
            'passenger_source': self.passenger_source,
            'maintenance_source': self.maintenance_source,
            'ir_passenger_count': self.ir_passenger_count,
            'yolo_passenger_count': self.yolo_passenger_count,
            'passenger_reconciliation_strategy': self.passenger_reconciliation_strategy,
            'is_simulated': self.is_simulated,
            'device_mac': self.device_mac,
            'image_url': (
                '/assets/images/electric_smart_bus.jpg' if ('Citaro' in (self.model or '') or 'Electric' in (self.model or '')) else
                '/assets/images/bus_sunset_coach.jpg' if '303' in (self.bus_number or '') else
                '/assets/images/volvo_luxury_bus.jpg' if ('SB-101' in (self.bus_number or '') or 'Volvo' in (self.model or '')) else
                '/assets/images/hero_luxury_coach.jpg'
            ),
            'last_ping': self.last_ping.isoformat() if self.last_ping else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PassengerLog(db.Model):
    __tablename__ = 'passenger_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    entries_count = db.Column(db.Integer, default=0)
    exits_count = db.Column(db.Integer, default=0)
    total_passengers = db.Column(db.Integer, nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=True)
    trigger_source = db.Column(db.String(20), default='IR_SENSOR') # IR_SENSOR, YOLO_CV, SIMULATION, MANUAL

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'entries_count': self.entries_count,
            'exits_count': self.exits_count,
            'total_passengers': self.total_passengers,
            'stop_id': self.stop_id,
            'trigger_source': self.trigger_source
        }


class TelemetryLog(db.Model):
    __tablename__ = 'telemetry_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float, default=0.0)
    heading = db.Column(db.Float, default=0.0)
    altitude = db.Column(db.Float, default=0.0)
    battery_voltage = db.Column(db.Float, default=12.6)
    engine_temp = db.Column(db.Float, default=85.0)
    fuel_level = db.Column(db.Float, default=80.0)
    passenger_count = db.Column(db.Integer, default=0)
    ir_count = db.Column(db.Integer, default=0)
    yolo_count = db.Column(db.Integer, default=0)
    source = db.Column(db.String(20), default='ESP32') # ESP32, SIMULATOR, MANUAL
    gps_source = db.Column(db.String(20), default='REAL') # REAL, SIMULATED
    passenger_source = db.Column(db.String(20), default='REAL') # REAL, SIMULATED
    maintenance_source = db.Column(db.String(20), default='MANUAL') # MANUAL, SIMULATED

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'speed': self.speed,
            'heading': self.heading,
            'altitude': self.altitude,
            'battery_voltage': self.battery_voltage,
            'engine_temp': self.engine_temp,
            'fuel_level': self.fuel_level,
            'passenger_count': self.passenger_count,
            'ir_count': self.ir_count,
            'yolo_count': self.yolo_count,
            'source': self.source,
            'gps_source': self.gps_source,
            'passenger_source': self.passenger_source,
            'maintenance_source': self.maintenance_source
        }


class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=True, index=True)
    alert_type = db.Column(db.String(50), nullable=False) # SOS, OVERCROWDING, OVERSPEED, DRIVER_DROWSINESS, ENGINE_OVERHEAT, LOW_BATTERY, ROUTE_DEVIATION, BROADCAST
    severity = db.Column(db.String(20), default='WARNING') # INFO, WARNING, HIGH, CRITICAL
    message = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, ACKNOWLEDGED, RESOLVED
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else ('All Fleet / All Passengers' if not self.bus_id else f'Bus #{self.bus_id}'),
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'status': self.status,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by
        }


class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False) # BATTERY, BRAKES, ENGINE_OIL, TIRES, TRANSMISSION, COOLANT
    degradation_score = db.Column(db.Float, default=15.0) # 0 to 100 (% degraded)
    health_percentage = db.Column(db.Float, default=85.0) # 100 - degradation
    rul_days = db.Column(db.Integer, default=60) # Remaining Useful Life in days
    status = db.Column(db.String(20), default='NORMAL') # NORMAL, ATTENTION, CRITICAL, SERVICED
    predicted_failure_date = db.Column(db.String(50), nullable=True)
    description = db.Column(db.String(255), default='Component functioning within nominal parameters.')
    last_serviced_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    bus = db.relationship('Bus', backref='maintenance_records')

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else f'Bus #{self.bus_id}',
            'component': self.component,
            'degradation_score': round(self.degradation_score, 1),
            'health_percentage': round(self.health_percentage, 1),
            'rul_days': self.rul_days,
            'status': self.status,
            'predicted_failure_date': self.predicted_failure_date,
            'description': self.description,
            'last_serviced_date': self.last_serviced_date.strftime('%Y-%m-%d') if self.last_serviced_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CameraEvent(db.Model):
    __tablename__ = 'camera_events'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = db.Column(db.String(50), default='PERSON_COUNT') # PERSON_COUNT, DROWSINESS_MONITOR, SNAPSHOT
    detected_person_count = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Float, default=0.90)
    bounding_boxes_json = db.Column(db.Text, default='[]')
    image_url = db.Column(db.String(255), nullable=True)
    details_json = db.Column(db.Text, default='{}')

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else f'Bus #{self.bus_id}',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'event_type': self.event_type,
            'detected_person_count': self.detected_person_count,
            'confidence': round(self.confidence, 2),
            'bounding_boxes': json.loads(self.bounding_boxes_json) if self.bounding_boxes_json else [],
            'image_url': self.image_url,
            'details': json.loads(self.details_json) if self.details_json else {}
        }


class DriverSafetyEvent(db.Model):
    __tablename__ = 'driver_safety_events'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False, index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = db.Column(db.String(50), default='DRIVER_DROWSINESS') # DRIVER_DROWSINESS, PROLONGED_EYE_CLOSURE, INACTIVITY, DISTRACTION
    severity = db.Column(db.String(20), default='HIGH') # INFO, WARNING, HIGH, CRITICAL
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, ACKNOWLEDGED, RESOLVED
    confidence = db.Column(db.Float, default=0.92)
    ear_score = db.Column(db.Float, default=0.18)
    message = db.Column(db.String(255), nullable=False)
    hardware_command_sent = db.Column(db.String(100), default='LED:RED;BUZZER:ON;LCD:DROWSY DRIVER')

    driver = db.relationship('Driver', backref='driver_safety_events')

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else f'Bus #{self.bus_id}',
            'driver_id': self.driver_id,
            'driver_name': self.driver.name if self.driver else 'Unassigned',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'event_type': self.event_type,
            'severity': self.severity,
            'status': self.status,
            'confidence': round(self.confidence, 2),
            'ear_score': round(self.ear_score, 2),
            'message': self.message,
            'hardware_command_sent': self.hardware_command_sent
        }


class MaintenanceAssessment(db.Model):
    __tablename__ = 'maintenance_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    assessed_by = db.Column(db.String(50), default='RULE_ENGINE') # MANUAL_ADMIN, RULE_ENGINE, ML_PREDICTIVE
    overall_health_score = db.Column(db.Float, default=85.0)
    maintenance_priority = db.Column(db.String(20), default='NORMAL') # LOW, MEDIUM, HIGH, CRITICAL
    recommendation = db.Column(db.String(50), default='KEEP_IN_OPERATION') # KEEP_IN_OPERATION, MONITOR, SERVICE_RECOMMENDED, CRITICAL_MAINTENANCE, REPLACE_STANDBY
    rule_findings_json = db.Column(db.Text, default='[]')
    ml_predictions_json = db.Column(db.Text, default='[]')
    status = db.Column(db.String(20), default='ACTIVE')

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else f'Bus #{self.bus_id}',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'assessed_by': self.assessed_by,
            'overall_health_score': round(self.overall_health_score, 1),
            'maintenance_priority': self.maintenance_priority,
            'recommendation': self.recommendation,
            'rule_findings': json.loads(self.rule_findings_json) if self.rule_findings_json else [],
            'ml_predictions': json.loads(self.ml_predictions_json) if self.ml_predictions_json else [],
            'status': self.status
        }


class FleetRecommendation(db.Model):
    __tablename__ = 'fleet_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=True, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    category = db.Column(db.String(50), default='MAINTENANCE_SWAP') # MAINTENANCE_SWAP, HIGH_DEMAND_DISPATCH, STANDBY_BUFFER, SCHEDULE_ADJUSTMENT
    priority = db.Column(db.String(20), default='MEDIUM') # LOW, MEDIUM, HIGH, CRITICAL
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    recommended_action = db.Column(db.String(100), default='Review Dispatch')
    target_route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    standby_bus_id = db.Column(db.Integer, nullable=True)
    is_applied = db.Column(db.Boolean, default=False)

    bus = db.relationship('Bus', foreign_keys=[bus_id])
    target_route = db.relationship('Route', foreign_keys=[target_route_id])

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'bus_number': self.bus.bus_number if self.bus else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'category': self.category,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'recommended_action': self.recommended_action,
            'target_route_id': self.target_route_id,
            'target_route_number': self.target_route.route_number if self.target_route else None,
            'standby_bus_id': self.standby_bus_id,
            'is_applied': self.is_applied
        }


class RfidCard(db.Model):
    __tablename__ = 'rfid_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    card_uid = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    card_holder_name = db.Column(db.String(100), default='Registered Passenger')
    balance = db.Column(db.Float, default=150.0)
    card_type = db.Column(db.String(20), default='PASSENGER') # PASSENGER, DRIVER, STOP_MARKER
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, BLOCKED, EXPIRED
    last_tapped_at = db.Column(db.DateTime, nullable=True)
    last_bus_id = db.Column(db.Integer, nullable=True)

    user = db.relationship('User', backref='rfid_cards')

    def to_dict(self):
        return {
            'id': self.id,
            'card_uid': self.card_uid,
            'user_id': self.user_id,
            'card_holder_name': self.card_holder_name,
            'balance': round(self.balance, 2),
            'card_type': self.card_type,
            'status': self.status,
            'last_tapped_at': self.last_tapped_at.isoformat() if self.last_tapped_at else None,
            'last_bus_id': self.last_bus_id
        }


class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=True)
    passenger_name = db.Column(db.String(100), default='Anonymous Passenger')
    rating = db.Column(db.Integer, default=5)
    category = db.Column(db.String(50), default='Punctuality') # Punctuality, Cleanliness, Driver Behavior, Comfort, Lost Item
    comments = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'bus_id': self.bus_id,
            'passenger_name': self.passenger_name,
            'rating': self.rating,
            'category': self.category,
            'comments': self.comments,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    sender = db.Column(db.String(10), default='USER') # USER, AI
    message = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, default=1.0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'sender': self.sender,
            'message': self.message,
            'intent': self.intent,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

