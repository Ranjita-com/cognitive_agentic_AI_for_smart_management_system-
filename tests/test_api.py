import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.app import create_app
from database.db import db

def test_health_api():
    app = create_app(Config)
    client = app.test_client()
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    print("PASS: test_health_api")

def test_buses_api():
    app = create_app(Config)
    client = app.test_client()
    res = client.get('/api/buses')
    assert res.status_code == 200
    data = res.get_json()
    assert data['count'] >= 4
    assert len(data['buses']) >= 4
    print("PASS: test_buses_api")

def test_routes_and_stops_api():
    app = create_app(Config)
    client = app.test_client()
    res_r = client.get('/api/routes')
    assert res_r.status_code == 200
    assert res_r.get_json()['count'] >= 3

    res_s = client.get('/api/stops')
    assert res_s.status_code == 200
    assert res_s.get_json()['count'] >= 10
    print("PASS: test_routes_and_stops_api")

def test_alerts_api():
    app = create_app(Config)
    client = app.test_client()
    res = client.get('/api/alerts')
    assert res.status_code == 200
    print("PASS: test_alerts_api")

def test_broadcast_alert_api():
    app = create_app(Config)
    client = app.test_client()
    payload = {
        'message': 'Severe rain near Central Station. Reduce speed on Route 101 to 30 km/h.',
        'severity': 'INFO',
        'alert_type': 'BROADCAST'
    }
    res = client.post('/api/alerts/broadcast', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['alert']['alert_type'] == 'BROADCAST'
    assert 'Severe rain' in data['alert']['message']

    # Verify it is returned in GET /api/alerts
    res_get = client.get('/api/alerts')
    assert res_get.status_code == 200
    alerts = res_get.get_json()['alerts']
    assert any(a['message'] == payload['message'] for a in alerts)
    print("PASS: test_broadcast_alert_api")

def test_passenger_search_api():
    app = create_app(Config)
    client = app.test_client()
    res = client.get('/api/passenger/search?origin=Tech&destination=Railway')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    print("PASS: test_passenger_search_api")

def test_passenger_timetable_api():
    app = create_app(Config)
    client = app.test_client()
    res = client.get('/api/passenger/timetable')
    assert res.status_code == 200
    assert len(res.get_json()['timetables']) >= 3
    print("PASS: test_passenger_timetable_api")

def test_chatbot_api():
    app = create_app(Config)
    client = app.test_client()

    queries = [
        ("Where is BS-102 right now?", ["SB-102", "km/h", "seats free"]),
        ("where is bs102", ["SB-102"]),
        ("How many minutes until the next bus arrives at my stop?", ["minutes", "arrival"]),
        ("Did I just miss the Bus 10B, or is it running late?", ["schedule", "minutes"]),
        ("Which bus stop is the closest to me right now?", ["Nearest Transit Stops", "Hospital Stop"]),
        ("Is the upcoming bus full or crowded?", ["Occupancy", "seats free"]),
        ("Are there any empty seats left on the next bus?", ["seats free"]),
        ("Can I fit a stroller/wheelchair on the bus coming in 5 minutes?", ["Accessibility", "Wheelchair", "Ramp"]),
        ("Why is my bus stopped? Is there traffic or an accident?", ["traffic", "route"]),
        ("Is my normal route blocked today?", ["route"]),
        ("Has the bus route been changed or detoured?", ["route"]),
        ("What is the fastest way to get to the downtown mall from here?", ["Route 303", "South Commercial Mall"]),
        ("How much will my ticket cost for this trip?", ["₹30.00", "₹65.00", "₹20.00", "RFID"]),
        ("What time does the last bus run tonight?", ["11:30 PM", "06:00 AM"])
    ]

    for q, expected_keywords in queries:
        res = client.post('/api/chatbot/message', json={'message': q})
        assert res.status_code == 200, f"Chatbot query failed for: {q}"
        reply = res.get_json().get('reply', '')
        for kw in expected_keywords:
            assert kw.lower() in reply.lower(), f"Expected '{kw}' in reply for query '{q}', got: {reply}"

    print("PASS: test_chatbot_api (All passenger queries & BS-102 alias verified!)")

def test_bus_swap_and_creation_api():
    import time
    app = create_app(Config)
    client = app.test_client()
    
    unique_bus_no = f"SB-TEST-{int(time.time())}"
    # 1. Test Bus creation with Route and Driver
    new_bus_data = {
        'bus_number': unique_bus_no,
        'capacity': 48,
        'model': 'Tata Starbus EV',
        'route_id': '101',
        'driver_id': 'Michael Vance'
    }
    res = client.post('/api/buses', json=new_bus_data)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.get_data(as_text=True)}"
    created = res.get_json()['bus']
    assert created['bus_number'] == unique_bus_no
    assert created['route_id'] is not None
    assert created['driver_id'] is not None
    assert 'fare' in created or 'ticket_price' in created

    # 2. Test Bus Swap API
    swap_data = {
        'bus1_id': 'SB-102',
        'bus2_id': 'SB-103',
        'reason': 'Scheduled battery charging swap'
    }
    res_swap = client.post('/api/buses/swap', json=swap_data)
    assert res_swap.status_code == 200
    swap_res = res_swap.get_json()
    assert swap_res['success'] is True
    assert 'swapped' in swap_res['message'].lower()

    # Clean up test bus
    del_res = client.delete(f"/api/buses/{created['id']}")
    assert del_res.status_code == 200
    print("PASS: test_bus_swap_and_creation_api")

def test_driver_face_ear_mar_inactivity_api():
    app = create_app(Config)
    client = app.test_client()

    # 1. Test FULLY INACTIVE: Open full mouth (MAR >= 0.50) AND Close eyes (EAR < 0.20) -> Swap Needed
    res_crit = client.post('/api/drivers/inspect-face', json={
        'bus_number': 'SB-101',
        'ear': 0.12,
        'mar': 0.60
    })
    assert res_crit.status_code == 200
    data_crit = res_crit.get_json()
    assert data_crit['attentiveness_state'] == 'FULLY_INACTIVE'
    assert data_crit['severity'] == 'CRITICAL'
    assert data_crit['driver_swap_recommended'] is True
    assert 'swap' in data_crit['status_message'].lower() or 'exchange' in data_crit['status_message'].lower()

    # 2. Test SLIGHTLY INACTIVE: Only open mouth (MAR >= 0.50, EAR normal) -> Warning
    res_warn_yawn = client.post('/api/drivers/inspect-face', json={
        'bus_number': 'SB-101',
        'ear': 0.30,
        'mar': 0.55
    })
    assert res_warn_yawn.status_code == 200
    data_warn_yawn = res_warn_yawn.get_json()
    assert data_warn_yawn['attentiveness_state'] == 'SLIGHTLY_INACTIVE'
    assert data_warn_yawn['severity'] == 'WARNING'
    assert data_warn_yawn['driver_swap_recommended'] is False

    # 3. Test SLIGHTLY INACTIVE: Only close eyes (EAR < 0.20, MAR normal) -> Warning
    res_warn_eye = client.post('/api/drivers/inspect-face', json={
        'bus_number': 'SB-101',
        'ear': 0.16,
        'mar': 0.14
    })
    assert res_warn_eye.status_code == 200
    data_warn_eye = res_warn_eye.get_json()
    assert data_warn_eye['attentiveness_state'] == 'SLIGHTLY_INACTIVE'
    assert data_warn_eye['severity'] == 'WARNING'

    # 4. Test ACTIVE: Eyes open (EAR >= 0.25) AND Mouth closed (MAR < 0.40) -> Normal
    res_active = client.post('/api/drivers/inspect-face', json={
        'bus_number': 'SB-101',
        'ear': 0.32,
        'mar': 0.14
    })
    assert res_active.status_code == 200
    data_active = res_active.get_json()
    assert data_active['attentiveness_state'] == 'ACTIVE'
    assert data_active['severity'] == 'INFO'
    assert data_active['is_drowsy'] is False

    print("PASS: test_driver_face_ear_mar_inactivity_api (EAR + MAR Multi-Tier Inactivity Verified!)")

if __name__ == '__main__':
    test_health_api()
    test_buses_api()
    test_routes_and_stops_api()
    test_alerts_api()
    test_broadcast_alert_api()
    test_passenger_search_api()
    test_passenger_timetable_api()
    test_chatbot_api()
    test_bus_swap_and_creation_api()
    test_driver_face_ear_mar_inactivity_api()
    print("ALL API TESTS PASSED!")


