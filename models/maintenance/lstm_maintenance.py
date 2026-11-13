import numpy as np
from datetime import datetime, timedelta

class LSTMMaintenanceModel:
    """
    LSTM-inspired Time-Series Degradation & Remaining Useful Life (RUL) Prediction Engine.
    Models continuous degradation curves for Battery, Brakes, Engine Oil, Tires, and Transmission.
    """
    def __init__(self):
        self.components = ['BATTERY', 'ENGINE_OIL', 'BRAKES', 'TIRES', 'TRANSMISSION']

    def forecast_degradation(self, voltage_series, temp_series, speed_series, mileage_km=45000):
        """
        Processes multi-feature time series to estimate component health percentages and failure dates.
        """
        avg_v = float(np.mean(voltage_series)) if voltage_series else 12.6
        min_v = float(np.min(voltage_series)) if voltage_series else 12.4
        avg_t = float(np.mean(temp_series)) if temp_series else 85.0
        max_t = float(np.max(temp_series)) if temp_series else 88.0

        results = []

        # 1. Battery Degradation
        v_loss = max(0.0, (12.6 - min_v) / 1.4) * 65.0
        t_stress = max(0.0, (max_t - 85.0) / 20.0) * 15.0
        bat_deg = min(98.0, max(5.0, v_loss + t_stress))
        bat_hlth = 100.0 - bat_deg
        bat_rul = int(max(3, (bat_hlth / 100.0) * 365))
        results.append({
            'component': 'BATTERY',
            'health_percentage': round(bat_hlth, 1),
            'degradation_score': round(bat_deg, 1),
            'rul_days': bat_rul,
            'predicted_failure_date': (datetime.now() + timedelta(days=bat_rul)).strftime('%Y-%m-%d'),
            'status': 'CRITICAL' if bat_hlth < 30 else ('ATTENTION' if bat_hlth < 60 else 'NORMAL')
        })

        # 2. Engine Oil Degradation
        oil_thermal = max(0.0, (avg_t - 80.0) / 25.0) * 55.0
        oil_deg = min(95.0, max(8.0, oil_thermal + ((mileage_km % 15000) / 15000.0) * 35.0))
        oil_hlth = 100.0 - oil_deg
        oil_rul = int(max(5, (oil_hlth / 100.0) * 180))
        results.append({
            'component': 'ENGINE_OIL',
            'health_percentage': round(oil_hlth, 1),
            'degradation_score': round(oil_deg, 1),
            'rul_days': oil_rul,
            'predicted_failure_date': (datetime.now() + timedelta(days=oil_rul)).strftime('%Y-%m-%d'),
            'status': 'CRITICAL' if oil_hlth < 30 else ('ATTENTION' if oil_hlth < 60 else 'NORMAL')
        })

        # 3. Brakes Wear
        brake_deg = min(90.0, max(10.0, ((mileage_km % 30000) / 30000.0) * 75.0))
        brake_hlth = 100.0 - brake_deg
        brake_rul = int(max(7, (brake_hlth / 100.0) * 240))
        results.append({
            'component': 'BRAKES',
            'health_percentage': round(brake_hlth, 1),
            'degradation_score': round(brake_deg, 1),
            'rul_days': brake_rul,
            'predicted_failure_date': (datetime.now() + timedelta(days=brake_rul)).strftime('%Y-%m-%d'),
            'status': 'CRITICAL' if brake_hlth < 25 else ('ATTENTION' if brake_hlth < 55 else 'NORMAL')
        })

        # 4. Tires Tread Wear
        tire_deg = min(85.0, max(5.0, ((mileage_km % 40000) / 40000.0) * 70.0))
        tire_hlth = 100.0 - tire_deg
        tire_rul = int(max(10, (tire_hlth / 100.0) * 300))
        results.append({
            'component': 'TIRES',
            'health_percentage': round(tire_hlth, 1),
            'degradation_score': round(tire_deg, 1),
            'rul_days': tire_rul,
            'predicted_failure_date': (datetime.now() + timedelta(days=tire_rul)).strftime('%Y-%m-%d'),
            'status': 'NORMAL' if tire_hlth > 60 else 'ATTENTION'
        })

        # 5. Transmission
        trans_deg = min(75.0, max(5.0, ((mileage_km % 50000) / 50000.0) * 50.0))
        trans_hlth = 100.0 - trans_deg
        trans_rul = int(max(15, (trans_hlth / 100.0) * 450))
        results.append({
            'component': 'TRANSMISSION',
            'health_percentage': round(trans_hlth, 1),
            'degradation_score': round(trans_deg, 1),
            'rul_days': trans_rul,
            'predicted_failure_date': (datetime.now() + timedelta(days=trans_rul)).strftime('%Y-%m-%d'),
            'status': 'NORMAL'
        })

        return results

lstm_maintenance_model = LSTMMaintenanceModel()
