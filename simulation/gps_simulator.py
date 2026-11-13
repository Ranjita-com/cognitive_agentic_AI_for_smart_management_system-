import random
import math

class GPSSimulator:
    """
    Simulates high-precision GPS coordinate movements, polyline traversal,
    heading, speed fluctuations, and stop proximity detection.
    """
    def __init__(self, speed_range=(30.0, 50.0)):
        self.speed_range = speed_range

    def advance_position(self, polyline, current_idx, sub_step, direction=1, speed_multiplier=1.0):
        """
        Advances position along polyline using smooth linear interpolation.
        Returns: (new_lat, new_lng, new_idx, new_sub_step, new_direction, speed, heading)
        """
        if not polyline or len(polyline) < 2:
            return (12.9716, 77.5946, 0, 0.0, 1, 0.0, 0.0)

        idx = current_idx % len(polyline)
        p1 = polyline[idx]
        next_idx = (idx + direction) % len(polyline)
        p2 = polyline[next_idx]

        sub_step += 0.25 * speed_multiplier
        if sub_step >= 1.0:
            sub_step = 0.0
            idx = next_idx
            if idx >= len(polyline) - 1:
                direction = -1
            elif idx <= 0:
                direction = 1

        t = min(1.0, sub_step)
        lat = p1[0] + (p2[0] - p1[0]) * t
        lng = p1[1] + (p2[1] - p1[1]) * t

        d_lat = p2[0] - p1[0]
        heading = 45.0 if d_lat >= 0 else 225.0
        speed = random.uniform(*self.speed_range) * min(1.5, speed_multiplier)

        return (lat, lng, idx, sub_step, direction, speed, heading)

    def is_near_stop(self, bus_lat, bus_lng, stop_lat, stop_lng, threshold_km=0.04):
        """Checks if bus is within threshold distance of a stop."""
        d = ((bus_lat - stop_lat)**2 + (bus_lng - stop_lng)**2)**0.5 * 111.0 # Approximate km
        return d <= threshold_km
