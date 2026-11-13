import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.app import create_app
from models.db_models import Bus
from agents.passenger_agent import passenger_agent
from agents.safety_agent import safety_agent
from agents.fleet_agent import fleet_agent
from agents.maintenance_agent import maintenance_agent
from models.driver_monitoring.driver_safety_model import driver_safety_model
from models.passenger_counting.crowd_predictor import crowd_predictor
from models.maintenance.lstm_maintenance import lstm_maintenance_model

def test_all_four_agents():
    app = create_app(Config)
    with app.app_context():
        # 1. Passenger Agent
        eta = passenger_agent.calculate_eta(1)
        assert eta.get('eta_minutes') is not None
        assert eta.get('distance_km') is not None
        print(f"PASS: Passenger Agent Dynamic ETA ({eta['eta_minutes']} mins)")

        chat = passenger_agent.process_chat_message("How much is the fare for Route 101?")
        assert 'Route 101' in chat['reply']
        print(f"PASS: Passenger Agent NLP Chatbot (Intent: {chat['intent']})")

        # 2. Safety Agent
        bus = Bus.query.filter_by(id=1).first()
        safety = safety_agent.evaluate_bus_safety(bus)
        assert safety.get('safety_score') is not None
        assert safety.get('hardware_control') is not None
        print(f"PASS: Safety Agent (Safety Score: {safety['safety_score']}%)")

        # 3. Fleet Optimization Agent
        recs = fleet_agent.generate_recommendations()
        assert isinstance(recs, list)
        print(f"PASS: Fleet Optimization Agent ({len(recs)} active recommendations)")

        # 4. Maintenance Agent
        maint = maintenance_agent.get_fleet_maintenance_summary()
        assert maint.get('fleet_health_index') is not None
        assert maint.get('total_buses_evaluated') >= 4
        print(f"PASS: Maintenance Agent (Fleet Health: {maint['fleet_health_index']}%)")


def test_modular_ml_models():
    # Test Driver Safety Model
    score_res = driver_safety_model.score_driver_behavior(speed=42.0, harsh_braking_events=0, violations_count=0)
    assert score_res['driver_score'] >= 90.0
    print(f"PASS: Driver Safety Model (Score: {score_res['driver_score']} - Risk: {score_res['risk_level']})")

    # Test Crowd Predictor Model
    crowd_res = crowd_predictor.predict_next_stop_occupancy(current_passengers=22, capacity=40, hour_of_day=8)
    assert crowd_res['expected_boardings'] > 0
    print(f"PASS: Crowd Predictor Model (Next Stop Pax: {crowd_res['predicted_passengers']}, Risk: {crowd_res['surge_risk']})")

    # Test LSTM Maintenance Degradation Model
    deg_res = lstm_maintenance_model.forecast_degradation([12.6, 12.5, 12.4], [84.0, 86.0, 85.0], [40.0, 45.0, 38.0])
    assert len(deg_res) == 5
    print(f"PASS: LSTM Maintenance Model ({len(deg_res)} components analyzed)")

if __name__ == '__main__':
    test_all_four_agents()
    test_modular_ml_models()
    print("ALL AGENT & ML TESTS PASSED!")
