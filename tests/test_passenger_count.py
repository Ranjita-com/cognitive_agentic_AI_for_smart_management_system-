import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from simulation.passenger_simulator import PassengerSimulator
from models.passenger_counting.crowd_predictor import crowd_predictor

def test_passenger_flux_simulation():
    sim = PassengerSimulator(default_capacity=40)
    current = 20
    new_count, entries, exits = sim.simulate_stop_flux(current, capacity=40)
    assert entries >= 0
    assert exits >= 0
    assert new_count == current + entries - exits
    print(f"PASS: Passenger Flux Simulation (Initial: {current}, +{entries}, -{exits} -> {new_count})")

def test_passenger_surge_and_overcrowding():
    sim = PassengerSimulator(default_capacity=40)
    surge_count, entries, exits = sim.trigger_passenger_surge(current_passengers=25, capacity=40)
    assert surge_count >= 40
    print(f"PASS: Passenger Surge Injection ({surge_count}/40 passengers)")

def test_crowd_predictor_model():
    pred_morning = crowd_predictor.predict_next_stop_occupancy(current_passengers=25, capacity=40, hour_of_day=8)
    assert pred_morning['surge_risk'] in ['LOW', 'MEDIUM', 'HIGH']
    assert pred_morning['expected_boardings'] > 0
    print(f"PASS: Crowd Predictor ML Model (Hour 8: {pred_morning['predicted_passengers']} pax, Risk: {pred_morning['surge_risk']})")

    pred_night = crowd_predictor.predict_next_stop_occupancy(current_passengers=5, capacity=40, hour_of_day=2)
    assert pred_night['surge_risk'] == 'LOW'
    print(f"PASS: Crowd Predictor Low Load (Hour 2: {pred_night['predicted_passengers']} pax, Risk: {pred_night['surge_risk']})")

if __name__ == '__main__':
    test_passenger_flux_simulation()
    test_passenger_surge_and_overcrowding()
    test_crowd_predictor_model()
    print("ALL PASSENGER COUNTING TESTS PASSED!")
