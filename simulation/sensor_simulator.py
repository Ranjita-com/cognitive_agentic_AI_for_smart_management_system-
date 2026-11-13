import random

class SensorSimulator:
    """
    Simulates realistic onboard vehicle telemetry (Battery voltage ADC, Engine temperature, Fuel level, Tire pressure).
    """
    def __init__(self):
        self.nominal_voltage = 12.6
        self.nominal_temp = 84.0

    def update_telemetry(self, current_voltage, current_temp, current_fuel, current_psi, speed=0.0):
        """
        Calculates realistic sensor telemetry fluctuations.
        """
        # Battery fluctuates between 11.5V and 12.8V
        v_delta = random.uniform(-0.02, 0.02)
        new_voltage = max(11.5, min(12.8, current_voltage + v_delta))

        # Engine temp rises with speed, cools when stationary
        t_delta = 0.12 if speed > 35.0 else -0.08
        t_noise = random.uniform(-0.05, 0.05)
        new_temp = max(76.0, min(96.0, current_temp + t_delta + t_noise))

        # Fuel decreases slightly
        new_fuel = max(5.0, current_fuel - 0.004)

        # Tire pressure nominal around 32 PSI
        new_psi = max(30.0, min(33.5, current_psi + random.uniform(-0.02, 0.02)))

        return {
            'battery_voltage': round(new_voltage, 2),
            'engine_temp': round(new_temp, 1),
            'fuel_level': round(new_fuel, 1),
            'tire_pressure': round(new_psi, 1)
        }
