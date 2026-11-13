import random

class PassengerSimulator:
    """
    Simulates passenger boarding and alighting dynamics through dual optical IR sensors.
    """
    def __init__(self, default_capacity=40):
        self.default_capacity = default_capacity

    def simulate_stop_flux(self, current_passengers, capacity=None):
        """
        Simulates realistic passenger boardings and alightings at a bus stop.
        Returns: (new_count, entries, exits)
        """
        cap = capacity if capacity else self.default_capacity
        
        # Determine realistic entries & exits
        entries = random.randint(1, 4)
        exits = random.randint(0, min(current_passengers, 3))
        
        new_count = max(0, min(cap + 8, current_passengers + entries - exits))
        return (new_count, entries, exits)

    def trigger_passenger_surge(self, current_passengers, capacity=None):
        """Injects an instant overcrowding event."""
        cap = capacity if capacity else self.default_capacity
        new_count = min(cap + 10, cap + 6)
        entries = max(0, new_count - current_passengers)
        return (new_count, entries, 0)
