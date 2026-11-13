from backend.services.fleet_service import fleet_service, FleetService, haversine_dist
from models.db_models import Bus, Alert

class FleetOptimizationAgent:
    """
    Intelligent Fleet Optimization Agent responsible for:
    - GPS route deviation and geofence corridor tracking.
    - Bus headway monitoring & bunching regulation.
    - Automated bus allocation and maintenance recommendations based on multi-bus health scores.
    - Autonomous standby bus dispatch & degraded vehicle swap.
    """

    def __init__(self, deviation_threshold_meters=350.0):
        self.service = fleet_service

    def check_route_deviation(self, bus):
        return self.service.check_route_deviation(bus)

    def auto_reallocate_degraded_bus(self, degraded_bus, reason="Telemetry Health Failure", trigger_source="AI_MAINTENANCE_AGENT", replacement_bus_id=None):
        return self.service.auto_reallocate_degraded_bus(degraded_bus, reason=reason, replacement_bus_id=replacement_bus_id)

    def get_standby_buses(self):
        return Bus.query.filter(
            Bus.status.in_(['standby', 'idle']),
            Bus.health_score >= 70.0
        ).all()

    def get_reallocation_history(self, limit=20):
        alerts = Alert.query.filter_by(alert_type='AUTO_REALLOCATION').order_by(Alert.created_at.desc()).limit(limit).all()
        return [a.to_dict() for a in alerts]

    def generate_recommendations(self):
        return self.service.generate_automated_fleet_recommendations()

fleet_agent = FleetOptimizationAgent()

