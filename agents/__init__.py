from agents.passenger_agent import passenger_agent, PassengerAgent
from agents.safety_agent import safety_agent, SafetyAgent
from agents.fleet_agent import fleet_agent, FleetOptimizationAgent
from agents.maintenance_agent import maintenance_agent, MaintenanceAgent

class AgentOrchestrator:
    """
    Central Coordinator for the 4 Autonomous Intelligent Agents:
    - Passenger Agent
    - Safety Agent
    - Fleet Optimization Agent
    - Maintenance Agent
    """
    def __init__(self):
        self.passenger = passenger_agent
        self.safety = safety_agent
        self.fleet = fleet_agent
        self.maintenance = maintenance_agent

    def process_telemetry_tick(self, bus, telemetry_payload=None):
        """
        Executes pipeline across Safety, Fleet, and Maintenance agents on every incoming telemetry packet.
        """
        safety_result = self.safety.evaluate_bus_safety(bus, telemetry_payload)
        deviation_result = self.fleet.check_route_deviation(bus)
        maint_result = self.maintenance.evaluate_bus_telemetry(bus, telemetry_payload)
        
        return {
            'bus_id': bus.id,
            'safety': safety_result,
            'route_deviation': deviation_result,
            'maintenance': maint_result,
            'hardware_control': safety_result.get('hardware_control', {})
        }

orchestrator = AgentOrchestrator()
