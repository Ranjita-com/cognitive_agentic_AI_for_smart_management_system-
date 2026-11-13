import json
import math
from datetime import datetime, timezone
from database.db import db
from models.db_models import Bus, Route, Alert, FleetRecommendation

def haversine_dist(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class FleetService:
    """
    Fleet Optimization & Automated Dispatch Allocation Service.
    Analyzes fleet-wide health, real-time passenger occupancy, route demand, headway spacing,
    and automatically produces operational recommendations and autonomous standby bus swaps.
    """

    def __init__(self, deviation_threshold_meters=350.0):
        self.deviation_threshold_km = deviation_threshold_meters / 1000.0

    def check_route_deviation(self, bus):
        """Calculates distance from bus to planned route polyline."""
        if not bus.route or not bus.route.polyline_json:
            return {'deviated': False, 'min_distance_meters': 0}

        try:
            polyline = json.loads(bus.route.polyline_json)
        except Exception:
            polyline = []

        if not polyline or len(polyline) < 2:
            return {'deviated': False, 'min_distance_meters': 0}

        min_dist_km = min(haversine_dist(bus.current_lat, bus.current_lng, pt[0], pt[1]) for pt in polyline)
        is_deviated = min_dist_km > self.deviation_threshold_km

        if is_deviated:
            existing = Alert.query.filter_by(
                bus_id=bus.id,
                alert_type='ROUTE_DEVIATION',
                status='ACTIVE'
            ).first()
            if not existing:
                alert = Alert(
                    bus_id=bus.id,
                    alert_type='ROUTE_DEVIATION',
                    severity='WARNING',
                    message=f"Route deviation detected: {bus.bus_number} is {min_dist_km*1000:.0f}m away from route path ({bus.route.name}).",
                    status='ACTIVE',
                    latitude=bus.current_lat,
                    longitude=bus.current_lng
                )
                db.session.add(alert)
                db.session.commit()

        return {
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'deviated': is_deviated,
            'min_distance_meters': round(min_dist_km * 1000, 1)
        }

    def generate_automated_fleet_recommendations(self):
        """
        Evaluates all buses and generates clear, actionable fleet optimization recommendations.
        Factoring in: Bus health, Maintenance priority, Real/Simulated data sources,
        Passenger demand, Available seats, and Standby fleet buffer.
        """
        buses = Bus.query.all()
        routes = Route.query.filter_by(is_active=True).all()
        recommendations = []

        # Find best available standby buses in depot
        standby_pool = [
            b for b in buses
            if b.status in ['standby', 'idle'] and not b.emergency_status and b.health_score >= 75.0
        ]
        standby_pool.sort(key=lambda x: x.health_score, reverse=True)

        # 1. Bus-specific Health & Allocation Recommendations
        for b in buses:
            # Find a suggested replacement from standby pool (excluding self)
            candidate = next((sb for sb in standby_pool if sb.id != b.id), None)
            suggested_replacement = None
            if candidate:
                suggested_replacement = {
                    'bus_id': candidate.id,
                    'bus_number': candidate.bus_number,
                    'health_score': candidate.health_score,
                    'status': candidate.status,
                    'capacity': candidate.capacity,
                    'model': candidate.model
                }

            # Check for critical or degraded maintenance
            if b.maintenance_priority == 'CRITICAL' or b.health_score < 60.0:
                has_route = bool(b.route_id and b.status == 'active')
                rec = {
                    'bus_id': b.id,
                    'bus_number': b.bus_number,
                    'category': 'MAINTENANCE_SWAP',
                    'priority': 'HIGH',
                    'title': f'{b.bus_number} Requires Urgent Maintenance (Health: {b.health_score:.1f}%)',
                    'message': f'{b.bus_number} health is {b.health_score:.1f}% with {b.maintenance_priority} priority (Batt: {b.battery_voltage:.2f}V, Temp: {b.engine_temp:.1f}°C). '
                               + (f'AI Agent proposes replacing with standby {candidate.bus_number} ({candidate.health_score:.1f}% Health) on {b.route.name if b.route else "active route"}.' if candidate and has_route else 'Send to depot workshop immediately.'),
                    'recommended_action': f'Approve Swap with {candidate.bus_number}' if (candidate and has_route) else 'Send to Depot Maintenance',
                    'action': f'Approve Swap with {candidate.bus_number}' if (candidate and has_route) else 'Send to Maintenance',
                    'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED',
                    'can_reallocate': bool(candidate and has_route),
                    'degraded_bus': {
                        'bus_id': b.id,
                        'bus_number': b.bus_number,
                        'health_score': b.health_score,
                        'maintenance_priority': b.maintenance_priority,
                        'route_name': b.route.name if b.route else "None",
                        'route_number': b.route.route_number if b.route else "N/A",
                        'route_id': b.route_id,
                        'status': b.status
                    },
                    'suggested_replacement': suggested_replacement
                }
                recommendations.append(rec)

            elif b.maintenance_priority == 'SERVICE_REQUIRED' or b.health_score < 75.0:
                has_route = bool(b.route_id and b.status == 'active')
                rec = {
                    'bus_id': b.id,
                    'bus_number': b.bus_number,
                    'category': 'MAINTENANCE_SWAP',
                    'priority': 'MEDIUM',
                    'title': f'{b.bus_number} Service Warning (Health: {b.health_score:.1f}%)',
                    'message': f'{b.bus_number} health is {b.health_score:.1f}%. '
                               + (f'AI Agent recommends preemptively swapping with {candidate.bus_number} to prevent in-service breakdown.' if candidate and has_route else 'Avoid assigning to long express lines; schedule routine service.'),
                    'recommended_action': f'Approve Swap with {candidate.bus_number}' if (candidate and has_route) else 'Schedule Routine Service',
                    'action': f'Approve Swap with {candidate.bus_number}' if (candidate and has_route) else 'Schedule Service',
                    'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED',
                    'can_reallocate': bool(candidate and has_route),
                    'degraded_bus': {
                        'bus_id': b.id,
                        'bus_number': b.bus_number,
                        'health_score': b.health_score,
                        'maintenance_priority': b.maintenance_priority,
                        'route_name': b.route.name if b.route else "None",
                        'route_number': b.route.route_number if b.route else "N/A",
                        'route_id': b.route_id,
                        'status': b.status
                    },
                    'suggested_replacement': suggested_replacement
                }
                recommendations.append(rec)

            elif b.status in ['standby', 'idle'] and b.health_score >= 85.0:
                rec = {
                    'bus_id': b.id,
                    'bus_number': b.bus_number,
                    'category': 'STANDBY_BUFFER',
                    'priority': 'LOW',
                    'title': f'{b.bus_number} Prime Standby Unit ({b.health_score:.1f}%)',
                    'message': f'{b.bus_number} is in pristine health ({b.health_score:.1f}%). Highly suitable for high-demand route deployment or instant replacement swap.',
                    'recommended_action': 'Keep in Ready Standby Buffer',
                    'action': 'Ready for Swap',
                    'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED',
                    'can_reallocate': False,
                    'suggested_replacement': None
                }
                recommendations.append(rec)

            # High occupancy monitoring
            if b.status == 'active' and b.occupancy_rate >= 80.0:
                rec = {
                    'bus_id': b.id,
                    'bus_number': b.bus_number,
                    'category': 'HIGH_DEMAND_DISPATCH',
                    'priority': 'HIGH' if b.occupancy_rate >= 95.0 else 'MEDIUM',
                    'title': f'{b.bus_number} High Occupancy ({b.current_passengers}/{b.capacity})',
                    'message': f'{b.bus_number} is at {b.occupancy_rate:.0f}% capacity on {b.route.name if b.route else "route"}. Monitor passenger influx via {"Dual IR + YOLO Camera" if b.bus_number == "SB-101" else "Simulated Telemetry"}.',
                    'recommended_action': 'Monitor Passenger Influx',
                    'action': 'Monitor Occupancy',
                    'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED',
                    'can_reallocate': False,
                    'suggested_replacement': None
                }
                recommendations.append(rec)

        # 2. Save / Update in Database
        for rec in recommendations:
            existing = FleetRecommendation.query.filter_by(
                bus_id=rec.get('bus_id'),
                category=rec['category'],
                is_applied=False
            ).first()
            if not existing:
                db_rec = FleetRecommendation(
                    bus_id=rec.get('bus_id'),
                    category=rec['category'],
                    priority=rec['priority'],
                    title=rec['title'],
                    message=rec['message'],
                    recommended_action=rec['recommended_action']
                )
                db.session.add(db_rec)
        db.session.commit()

        return recommendations

    def auto_reallocate_degraded_bus(self, degraded_bus, reason="Telemetry Health Failure", replacement_bus_id=None):
        """
        Autonomous Intelligent Bus Reallocation:
        Swaps an unhealthy active bus with the best available healthy standby bus.
        """
        if not degraded_bus.route_id:
            return {'reallocated': False, 'message': f'Bus {degraded_bus.bus_number} has no active route assigned to swap.'}

        route = Route.query.get(degraded_bus.route_id)
        route_name = route.name if route else f"Route #{degraded_bus.route_id}"
        route_number = route.route_number if route else "N/A"

        replacement_bus = None
        if replacement_bus_id:
            replacement_bus = Bus.query.get(replacement_bus_id)
            if not replacement_bus or replacement_bus.id == degraded_bus.id:
                replacement_bus = None

        if not replacement_bus:
            # Find best healthy standby candidate
            candidate_buses = Bus.query.filter(
                Bus.id != degraded_bus.id,
                Bus.status.in_(['standby', 'idle']),
                Bus.emergency_status == False,
                Bus.health_score >= 70.0
            ).order_by(Bus.health_score.desc()).all()

            if not candidate_buses:
                return {'reallocated': False, 'message': f'No healthy standby buses available in depot to replace {degraded_bus.bus_number}.'}
            replacement_bus = candidate_buses[0]

        assigned_route_id = degraded_bus.route_id
        assigned_driver_id = degraded_bus.driver_id

        # Swap assignments
        replacement_bus.route_id = assigned_route_id
        replacement_bus.status = 'active'
        if not replacement_bus.driver_id and assigned_driver_id:
            replacement_bus.driver_id = assigned_driver_id

        replacement_bus.current_lat = degraded_bus.current_lat
        replacement_bus.current_lng = degraded_bus.current_lng
        replacement_bus.speed = 32.0
        replacement_bus.last_stop_id = degraded_bus.last_stop_id
        replacement_bus.next_stop_id = degraded_bus.next_stop_id

        degraded_bus.status = 'maintenance'
        degraded_bus.speed = 0.0
        degraded_bus.route_id = None

        # Physical serial alert for SB-101 if involved
        if degraded_bus.bus_number == 'SB-101':
            from backend.services.hardware_service import hardware_service
            hardware_service.send_serial_command("ALERT:AUTO_REALLOCATION;LCD:SWAPPED TO DEPOT;LED:RED;BUZZER:OFF")

        # Audit Alert
        realloc_alert = Alert(
            bus_id=degraded_bus.id,
            alert_type='AUTO_REALLOCATION',
            severity='CRITICAL',
            message=f"🤖 [AI AUTO-ALLOCATION APPROVED] Route {route_number} ({route_name}) successfully reassigned from degraded {degraded_bus.bus_number} (Health: {degraded_bus.health_score:.1f}%) to healthy standby {replacement_bus.bus_number} (Health: {replacement_bus.health_score:.1f}%). Reason: {reason}.",
            status='ACTIVE',
            latitude=degraded_bus.current_lat,
            longitude=degraded_bus.current_lng
        )
        db.session.add(realloc_alert)
        db.session.commit()

        # WebSockets broadcast
        try:
            from backend.sockets import socketio
            socketio.emit('bus_reallocated', {
                'degraded_bus': degraded_bus.to_dict(),
                'replacement_bus': replacement_bus.to_dict(),
                'route_number': route_number,
                'route_name': route_name,
                'reason': reason,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            socketio.emit('bus_update', {'bus': degraded_bus.to_dict()})
            socketio.emit('bus_update', {'bus': replacement_bus.to_dict()})
            socketio.emit('new_alert', {'alert': realloc_alert.to_dict()})
        except Exception:
            pass

        return {
            'success': True,
            'reallocated': True,
            'degraded_bus': degraded_bus.to_dict(),
            'replacement_bus': replacement_bus.to_dict(),
            'route_number': route_number,
            'route_name': route_name,
            'reason': reason,
            'message': f"Route {route_number} ({route_name}) successfully reassigned from {degraded_bus.bus_number} to {replacement_bus.bus_number}."
        }

fleet_service = FleetService()
