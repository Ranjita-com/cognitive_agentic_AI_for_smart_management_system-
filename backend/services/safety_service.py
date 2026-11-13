from datetime import datetime, timezone
from database.db import db
from models.db_models import Bus, Alert, Driver
from backend.services.hardware_service import hardware_service

class SafetyService:
    """
    Safety & Emergency Command Service.
    Monitors overcrowding, speed violations, driver attentiveness/drowsiness, and SOS alerts.
    Dispatches hardware control commands for physical IoT Bus SB-101.
    """

    def __init__(self, speed_limit_kmh=65.0):
        self.speed_limit = speed_limit_kmh

    def evaluate_safety(self, bus, telemetry_payload=None, is_drowsy=False):
        """
        Evaluates safety compliance for a bus upon receiving telemetry or driver safety events.
        """
        alerts = []
        capacity = bus.capacity if bus.capacity > 0 else 40
        passengers = bus.current_passengers
        occupancy_ratio = passengers / float(capacity)

        # 1. Overcrowding Check
        if occupancy_ratio >= 1.0:
            existing = Alert.query.filter_by(
                bus_id=bus.id,
                alert_type='OVERCROWDING',
                severity='CRITICAL',
                status='ACTIVE'
            ).first()
            if not existing:
                alert = Alert(
                    bus_id=bus.id,
                    alert_type='OVERCROWDING',
                    severity='CRITICAL',
                    message=f"CRITICAL OVERCROWDING on {bus.bus_number}: {passengers}/{capacity} passengers ({occupancy_ratio*100:.0f}% capacity)! [Source: {bus.passenger_source}]",
                    status='ACTIVE',
                    latitude=bus.current_lat,
                    longitude=bus.current_lng
                )
                db.session.add(alert)
                alerts.append(alert)

        elif occupancy_ratio >= 0.85:
            existing = Alert.query.filter_by(
                bus_id=bus.id,
                alert_type='OVERCROWDING',
                severity='WARNING',
                status='ACTIVE'
            ).first()
            if not existing:
                alert = Alert(
                    bus_id=bus.id,
                    alert_type='OVERCROWDING',
                    severity='WARNING',
                    message=f"High occupancy warning on {bus.bus_number}: {passengers}/{capacity} passengers ({occupancy_ratio*100:.0f}%).",
                    status='ACTIVE',
                    latitude=bus.current_lat,
                    longitude=bus.current_lng
                )
                db.session.add(alert)
                alerts.append(alert)

        # 2. Overspeeding Check
        if bus.speed > self.speed_limit:
            existing = Alert.query.filter_by(
                bus_id=bus.id,
                alert_type='OVERSPEED',
                status='ACTIVE'
            ).first()
            if not existing:
                alert = Alert(
                    bus_id=bus.id,
                    alert_type='OVERSPEED',
                    severity='HIGH',
                    message=f"Overspeed violation: {bus.bus_number} traveling at {bus.speed:.1f} km/h (Limit: {self.speed_limit:.0f} km/h).",
                    status='ACTIVE',
                    latitude=bus.current_lat,
                    longitude=bus.current_lng
                )
                db.session.add(alert)
                alerts.append(alert)
                if bus.driver:
                    bus.driver.safety_violations += 1

        # 3. SOS Check
        if bus.emergency_status:
            existing = Alert.query.filter_by(
                bus_id=bus.id,
                alert_type='SOS',
                status='ACTIVE'
            ).first()
            if not existing:
                alert = Alert(
                    bus_id=bus.id,
                    alert_type='SOS',
                    severity='CRITICAL',
                    message=f"EMERGENCY SOS TRIGGERED on {bus.bus_number}! Location: ({bus.current_lat:.4f}, {bus.current_lng:.4f})",
                    status='ACTIVE',
                    latitude=bus.current_lat,
                    longitude=bus.current_lng
                )
                db.session.add(alert)
                alerts.append(alert)

        # Dynamic Safety Score (100 base)
        score = 100.0
        if bus.emergency_status: score -= 50.0
        if is_drowsy: score -= 35.0
        if occupancy_ratio > 1.0: score -= (occupancy_ratio - 1.0) * 40.0
        elif occupancy_ratio > 0.85: score -= (occupancy_ratio - 0.85) * 15.0
        if bus.speed > self.speed_limit: score -= min(30.0, (bus.speed - self.speed_limit) * 1.5)

        bus.safety_score = max(10.0, min(100.0, score))
        db.session.commit()

        # Build hardware actuator command package
        hw_control = hardware_service.build_actuator_commands(
            passenger_count=bus.current_passengers,
            capacity=bus.capacity,
            is_emergency=bus.emergency_status,
            is_drowsy=is_drowsy
        )

        return {
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'safety_score': round(bus.safety_score, 1),
            'emergency_active': bus.emergency_status,
            'alerts': [a.to_dict() for a in alerts],
            'hardware_control': hw_control
        }

    def trigger_sos(self, bus_id, lat=None, lng=None):
        """Manually or remotely triggers Emergency SOS mode on a bus."""
        bus = Bus.query.get(bus_id)
        if not bus:
            return {'error': 'Bus not found'}

        bus.emergency_status = True
        bus.status = 'emergency'
        if lat and lng:
            bus.current_lat = lat
            bus.current_lng = lng

        alert = Alert(
            bus_id=bus.id,
            alert_type='SOS',
            severity='CRITICAL',
            message=f"EMERGENCY SOS ACTIVATED on Bus {bus.bus_number}! Immediate response required.",
            status='ACTIVE',
            latitude=bus.current_lat,
            longitude=bus.current_lng
        )
        db.session.add(alert)
        db.session.commit()

        hw_control = hardware_service.build_actuator_commands(
            passenger_count=bus.current_passengers,
            capacity=bus.capacity,
            is_emergency=True
        )

        return {
            'success': True,
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'alert': alert.to_dict(),
            'emergency_status': True,
            'hardware_control': hw_control
        }

    def resolve_emergency(self, bus_id, admin_user='Admin'):
        """Resolves active SOS emergency on a bus."""
        bus = Bus.query.get(bus_id)
        if not bus:
            return {'error': 'Bus not found'}

        bus.emergency_status = False
        bus.status = 'active'

        active_alerts = Alert.query.filter_by(bus_id=bus.id, alert_type='SOS', status='ACTIVE').all()
        for a in active_alerts:
            a.status = 'RESOLVED'
            a.resolved_at = datetime.now(timezone.utc)
            a.resolved_by = admin_user

        db.session.commit()
        return {'success': True, 'message': f'Emergency resolved for {bus.bus_number}'}

safety_service = SafetyService()
