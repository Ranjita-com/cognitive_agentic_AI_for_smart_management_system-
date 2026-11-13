class EmergencySimulator:
    """
    Simulates incident injection and fault diagnostics (Panic SOS, Engine Overheat, Battery Fault).
    """
    @staticmethod
    def create_sos_payload(bus_id, lat, lng):
        return {
            'bus_id': bus_id,
            'emergency_button': True,
            'latitude': lat,
            'longitude': lng,
            'status': 'emergency',
            'severity': 'CRITICAL',
            'message': f'EMERGENCY SOS INJECTED on Bus #{bus_id}'
        }

    @staticmethod
    def create_overheat_payload(bus_id, temp=98.5):
        return {
            'bus_id': bus_id,
            'engine_temp': temp,
            'severity': 'CRITICAL',
            'message': f'Engine Overheat condition simulated ({temp}°C).'
        }

    @staticmethod
    def create_low_battery_payload(bus_id, voltage=11.1):
        return {
            'bus_id': bus_id,
            'battery_voltage': voltage,
            'severity': 'CRITICAL',
            'message': f'Low Battery condition simulated ({voltage}V).'
        }
