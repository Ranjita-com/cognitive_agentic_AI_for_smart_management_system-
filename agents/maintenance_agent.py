from backend.services.maintenance_service import maintenance_service, MaintenanceService

class MaintenanceAgent:
    """
    Intelligent Vehicle Health & Maintenance Agent:
    - Analyzes manually entered & simulated maintenance data (battery, engine temp, tire pressure, brakes, engine, transmission).
    - Rule-based maintenance priority calculation (CRITICAL -> SERVICE_REQUIRED -> MONITOR -> NORMAL).
    - ML / LSTM Degradation Scoring & Remaining Useful Life (RUL) estimation.
    - Automated maintenance recommendations and service ticket generation to assist administrators.
    """

    def __init__(self, min_battery=11.4, max_temp=95.0):
        self.service = maintenance_service

    def evaluate_bus_telemetry(self, bus, telemetry_payload=None):
        """
        Evaluates current bus maintenance state using manual/simulated telemetry.
        """
        payload = telemetry_payload or {}
        return self.service.evaluate_manual_maintenance_input(
            bus_id=bus.id,
            battery_voltage=payload.get('battery_voltage', bus.battery_voltage),
            engine_temp=payload.get('engine_temp', bus.engine_temp),
            tire_pressure=payload.get('tire_pressure', bus.tire_pressure),
            brake_health=payload.get('brake_health', bus.brake_health),
            engine_health=payload.get('engine_health', bus.engine_health),
            transmission_health=payload.get('transmission_health', bus.transmission_health),
            notes=payload.get('notes', bus.maintenance_notes)
        )

    def manual_telemetry_inspection(self, bus_id, battery_voltage=None, engine_temp=None, tire_pressure=None,
                                    brake_health=None, engine_health=None, transmission_health=None, fuel_level=None, speed=None, notes=None):
        return self.service.evaluate_manual_maintenance_input(
            bus_id=bus_id,
            battery_voltage=battery_voltage,
            engine_temp=engine_temp,
            tire_pressure=tire_pressure,
            brake_health=brake_health,
            engine_health=engine_health,
            transmission_health=transmission_health,
            notes=notes
        )

    def reset_bus_health(self, bus_id):
        return self.service.reset_bus_service(bus_id)

    def get_fleet_maintenance_summary(self):
        priority_list = self.service.get_fleet_priority_ranking()
        avg_health = sum(p['health_score'] for p in priority_list) / len(priority_list) if priority_list else 90.0
        critical_count = sum(1 for p in priority_list if p['maintenance_priority'] == 'CRITICAL')
        attention_count = sum(1 for p in priority_list if p['maintenance_priority'] in ['SERVICE_REQUIRED', 'MONITOR'])

        return {
            'fleet_health_index': round(avg_health, 1),
            'total_buses_evaluated': len(priority_list),
            'critical_components': critical_count,
            'attention_required': attention_count,
            'priority_ranking': priority_list
        }

maintenance_agent = MaintenanceAgent()

