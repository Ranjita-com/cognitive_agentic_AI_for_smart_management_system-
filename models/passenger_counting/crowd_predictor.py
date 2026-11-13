import numpy as np

class CrowdPredictor:
    """
    Passenger Flow & Overcrowding Prediction Model.
    Predicts upcoming stop passenger boarding volumes and peak hour crowd surges.
    """
    def __init__(self):
        # Hourly baseline passenger load factors (0 to 23 hours)
        self.hourly_multipliers = [
            0.1, 0.05, 0.05, 0.1, 0.2, 0.5, 0.85, 1.4, 1.8, 1.2, 0.9, 0.8,
            1.0, 0.9, 0.85, 1.1, 1.6, 1.9, 1.7, 1.2, 0.8, 0.5, 0.3, 0.15
        ]

    def predict_next_stop_occupancy(self, current_passengers, capacity, hour_of_day=8):
        """
        Forecasts expected passenger load for the upcoming stop based on historical rush factors.
        """
        hour = max(0, min(23, int(hour_of_day)))
        multiplier = self.hourly_multipliers[hour]
        
        expected_boardings = int(random_board := max(1, 4 * multiplier + np.random.normal(0, 1)))
        expected_alightings = int(max(0, current_passengers * 0.18 + np.random.normal(0, 1)))

        predicted_load = max(0, min(capacity + 15, current_passengers + expected_boardings - expected_alightings))
        occupancy_rate = (predicted_load / float(capacity)) * 100.0

        return {
            'predicted_passengers': predicted_load,
            'expected_boardings': expected_boardings,
            'expected_alightings': expected_alightings,
            'occupancy_rate': round(occupancy_rate, 1),
            'surge_risk': 'HIGH' if occupancy_rate > 85.0 else ('MEDIUM' if occupancy_rate > 65.0 else 'LOW')
        }

crowd_predictor = CrowdPredictor()
