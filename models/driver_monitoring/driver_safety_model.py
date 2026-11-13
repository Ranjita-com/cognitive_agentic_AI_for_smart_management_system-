class DriverSafetyModel:
    """
    Driver Safety & Telemetric Behavior Monitoring Model.
    Evaluates speed compliance, harsh maneuvers, and safety violation scoring.
    """
    def __init__(self, speed_limit_kmh=65.0):
        self.speed_limit = speed_limit_kmh

    def score_driver_behavior(self, speed, harsh_braking_events=0, violations_count=0, shift_hours=4.0):
        """
        Calculates driver performance score (0-100) and risk category.
        """
        score = 100.0

        # Speed Penalty
        if speed > self.speed_limit:
            overspeed_delta = speed - self.speed_limit
            score -= min(35.0, overspeed_delta * 2.0)

        # Harsh Braking Penalty
        score -= min(25.0, harsh_braking_events * 5.0)

        # Historic Violations
        score -= min(20.0, violations_count * 4.0)

        # Fatigue factor for shifts > 6 hours
        if shift_hours > 6.0:
            score -= (shift_hours - 6.0) * 3.0

        final_score = max(10.0, min(100.0, score))
        risk_level = 'LOW' if final_score >= 85 else ('MODERATE' if final_score >= 65 else 'HIGH')

        return {
            'driver_score': round(final_score, 1),
            'risk_level': risk_level,
            'speed_compliant': speed <= self.speed_limit,
            'recommendation': 'Nominal driving pattern.' if risk_level == 'LOW' else 'Driver intervention or rest break recommended.'
        }

driver_safety_model = DriverSafetyModel()
