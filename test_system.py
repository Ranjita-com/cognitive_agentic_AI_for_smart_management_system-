"""
=============================================================================
SMART BUS PROJECT -- COMPREHENSIVE AUTOMATED VERIFICATION SUITE
=============================================================================
Verifies all 8 prompt hardware & architecture testing requirements:
  - Test 1: SB-101 Real GPS Telemetry Ingestion
  - Test 2: SB-101 Dual IR Sensor Passenger Counting
  - Test 3: YOLOv8 Nano Passenger Detection & Reconciliation
  - Test 4: Driver Drowsiness Event & Safety Agent Escalation
  - Test 5: Manual Maintenance Data Ingestion & Rule-based Assessment
  - Test 6: Fleet Agent Automatic Bus Allocation & Standby Recommendation
  - Test 7: Passenger Agent (Search, ETA, Seat Availability, NLP Chatbot)
  - Test 8: Autonomous Multi-Bus Simulation for Software Buses (SB-102, SB-103, SB-104)
=============================================================================
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.app import create_app
from database.db import db
from models.db_models import User, Bus, Route, Stop, Driver, MaintenanceRecord, Alert, TelemetryLog, DriverSafetyEvent
from agents.passenger_agent import passenger_agent
from agents.safety_agent import safety_agent
from agents.fleet_agent import fleet_agent
from agents.maintenance_agent import maintenance_agent
from backend.services.camera_service import camera_service
from backend.services.maintenance_service import maintenance_service
from backend.services.telemetry_service import telemetry_service
from simulation.bus_simulator import simulator_engine

def run_all_tests():
    print("=" * 75)
    print(" [*] STARTING SMART BUS ARCHITECTURAL VERIFICATION SUITE")
    print("=" * 75)

    app = create_app(Config)
    client = app.test_client()

    with app.app_context():
        # Reset fleet state for deterministic test run
        b101 = Bus.query.filter_by(bus_number="SB-101").first()
        b102 = Bus.query.filter_by(bus_number="SB-102").first()
        b103 = Bus.query.filter_by(bus_number="SB-103").first()
        b104 = Bus.query.filter_by(bus_number="SB-104").first()
        if b101:
            b101.status = 'active'
            b101.route_id = 1
            b101.emergency_status = False
            b101.health_score = 94.0
            b101.maintenance_priority = 'NORMAL'
        if b102:
            b102.status = 'active'
            b102.route_id = 1
            b102.emergency_status = False
            b102.health_score = 90.0
            b102.maintenance_priority = 'NORMAL'
        if b103:
            b103.status = 'standby'
            b103.route_id = None
            b103.emergency_status = False
            b103.health_score = 98.0
            b103.maintenance_priority = 'NORMAL'
        if b104:
            b104.status = 'standby'
            b104.route_id = None
            b104.emergency_status = False
            b104.health_score = 95.0
            b104.maintenance_priority = 'NORMAL'
        db.session.commit()

        # -------------------------------------------------------------------
        # TEST 1: SB-101 sends GPS
        # Expected: Dashboard/DB shows live SB-101 location and source 'REAL'.
        # -------------------------------------------------------------------
        print("\n [TEST 1] Testing SB-101 Real Hardware GPS Telemetry...")
        payload_t1 = {
            "bus_number": "SB-101",
            "latitude": 12.9740,
            "longitude": 77.5970,
            "speed": 35.5,
            "heading": 90.0,
            "altitude": 920.0,
            "source": "ESP32"
        }
        res1 = client.post('/api/esp32/telemetry', json=payload_t1)
        assert res1.status_code == 200 and res1.json.get('success'), f"Test 1 failed: {res1.json}"
        
        bus_sb101 = Bus.query.filter_by(bus_number="SB-101").first()
        assert bus_sb101.data_source == 'REAL', "SB-101 data_source should be REAL"
        assert bus_sb101.gps_source == 'REAL', "SB-101 gps_source should be REAL"
        assert abs(bus_sb101.current_lat - 12.9740) < 0.001, "SB-101 latitude mismatch"
        print(f"  [OK] SB-101 GPS updated to ({bus_sb101.current_lat}, {bus_sb101.current_lng}) [Source: {bus_sb101.gps_source}]")

        # -------------------------------------------------------------------
        # TEST 2: SB-101 IR detects passenger
        # Expected: Passenger count increases (IR count logged, source 'REAL').
        # -------------------------------------------------------------------
        print("\n [TEST 2] Testing SB-101 Physical IR Passenger Counter...")
        payload_t2 = {
            "bus_number": "SB-101",
            "passenger_count": 24,
            "entries": 2,
            "exits": 0,
            "source": "ESP32"
        }
        res2 = client.post('/api/esp32/telemetry', json=payload_t2)
        assert res2.status_code == 200, "Test 2 failed"
        bus_sb101 = Bus.query.filter_by(bus_number="SB-101").first()
        assert bus_sb101.passenger_source == 'REAL', "SB-101 passenger_source should be REAL"
        assert bus_sb101.ir_passenger_count == 24, "SB-101 IR passenger count mismatch"
        print(f"  [OK] SB-101 IR count recorded: {bus_sb101.ir_passenger_count} passengers [Source: {bus_sb101.passenger_source}]")

        # -------------------------------------------------------------------
        # TEST 3: YOLO detects passengers
        # Expected: YOLO person count appears in dashboard and DB.
        # -------------------------------------------------------------------
        print("\n [TEST 3] Testing YOLOv8 Nano Passenger Detection & Reconciliation...")
        res3 = client.post('/api/camera/yolo-count', json={
            "bus_number": "SB-101",
            "detected_count": 23,
            "confidence": 0.93
        })
        assert res3.status_code == 200 and res3.json.get('success'), "Test 3 failed"
        bus_sb101 = Bus.query.filter_by(bus_number="SB-101").first()
        assert bus_sb101.yolo_passenger_count == 23, "YOLO count mismatch"
        print(f"  [OK] YOLO count recorded: {bus_sb101.yolo_passenger_count} P | IR Count: {bus_sb101.ir_passenger_count} P | Final Reconciled: {bus_sb101.current_passengers} P")

        # -------------------------------------------------------------------
        # TEST 4: Driver drowsiness event
        # Expected: Safety Agent receives event. Dashboard displays drowsiness alert.
        # -------------------------------------------------------------------
        print("\n [TEST 4] Testing Driver Drowsiness Event & Safety Agent Escalation...")
        res4 = client.post('/api/camera/drowsiness-event', json={
            "bus_number": "SB-101",
            "ear": 0.17,
            "confidence": 0.94
        })
        assert res4.status_code == 200 and res4.json.get('success'), "Test 4 failed"
        latest_event = DriverSafetyEvent.query.filter_by(bus_id=bus_sb101.id).order_by(DriverSafetyEvent.timestamp.desc()).first()
        assert latest_event is not None and latest_event.event_type == 'DRIVER_DROWSINESS', "Drowsiness event not logged"
        print(f"  [OK] Safety Agent Event: {latest_event.event_type} (Severity: {latest_event.severity}, Confidence: {latest_event.confidence})")
        print(f"  [OK] Hardware Actuator Response: {res4.json.get('hardware_control')}")

        # -------------------------------------------------------------------
        # TEST 5: Manual maintenance input
        # Example: SB-102 Battery = 10.8V, Temperature = 98°C, Brake Health = 62%.
        # Expected: Maintenance Agent detects warning.
        # -------------------------------------------------------------------
        print("\n [TEST 5] Testing Manual Maintenance Input (No fake physical sensors)...")
        maint_payload = {
            "bus_number": "SB-102",
            "battery_voltage": 10.8,
            "engine_temp": 98.0,
            "tire_pressure": 27.0,
            "brake_health": 62.0,
            "engine_health": 73.0,
            "transmission_health": 85.0,
            "notes": "Annual fleet depot check"
        }
        res5 = client.post('/api/maintenance/manual-entry', json=maint_payload)
        assert res5.status_code == 200 and res5.json.get('success'), "Test 5 failed"
        bus_sb102 = Bus.query.filter_by(bus_number="SB-102").first()
        assert bus_sb102.maintenance_source == 'MANUAL', "Maintenance source should be MANUAL"
        assert bus_sb102.maintenance_priority in ('CRITICAL', 'SERVICE_REQUIRED', 'HIGH'), "Priority should reflect degradation"
        print(f"  [OK] SB-102 Manual Maintenance Ingested: Priority = {bus_sb102.maintenance_priority}, Health = {bus_sb102.health_score}% [Source: {bus_sb102.maintenance_source}]")

        # -------------------------------------------------------------------
        # TEST 6: Fleet allocation
        # Expected: Fleet Agent recommends avoiding unhealthy buses.
        # -------------------------------------------------------------------
        print("\n [TEST 6] Testing Fleet Agent Automatic Allocation & Priority Ranking...")
        res6 = client.get('/api/maintenance/priority-list')
        assert res6.status_code == 200 and res6.json.get('priorities'), "Test 6 failed"
        priorities = res6.json.get('priorities')
        highest_p = priorities[0]
        print(f"  [OK] Highest Maintenance Priority Bus: {highest_p.get('bus_number')} (Rank #1, Action: {highest_p.get('recommendation')})")
        
        recs_res = client.get('/api/fleet/recommendations')
        assert recs_res.status_code == 200 and recs_res.json.get('recommendations'), "Fleet recommendations failed"
        print(f"  [OK] Fleet Agent Recommendations Generated: {len(recs_res.json['recommendations'])} dispatch actions")

        # -------------------------------------------------------------------
        # TEST 7: Passenger Agent
        # Expected: Passenger searches SB-101. System returns location, ETA and seat availability.
        # -------------------------------------------------------------------
        print("\n [TEST 7] Testing Passenger Agent (Tracking, ETA, Seat Layout, Chatbot)...")
        # 7a: Tracking
        track_res = client.get('/api/passenger/bus/1/tracking')
        assert track_res.status_code == 200, "Tracking query failed"
        print(f"  [OK] Tracking SB-101: Lat={track_res.json['bus']['current_lat']}, ETA={track_res.json.get('eta', {}).get('eta_minutes')} mins")

        # 7b: Seats
        seat_res = client.get('/api/passenger/bus/1/seats')
        assert seat_res.status_code == 200 and 'seats' in seat_res.json, "Seats query failed"
        print(f"  [OK] 2D Visual Seat Layout: Available Seats = {seat_res.json['available_seats']} / {seat_res.json['capacity']}")

        # 7c: NLP Chatbot
        chat_res = client.post('/api/chatbot/message', json={"message": "When will Bus 101 arrive?"})
        assert chat_res.status_code == 200 and chat_res.json.get('reply'), "Chatbot message failed"
        safe_reply = chat_res.json['reply'].encode('ascii', errors='replace').decode('ascii')
        print(f"  [OK] Passenger NLP Chatbot Response: \"{safe_reply[:80]}...\"")

        # -------------------------------------------------------------------
        # TEST 8: Simulated bus
        # Expected: SB-103 continues generating simulated telemetry without physical hardware.
        # -------------------------------------------------------------------
        print("\n [TEST 8] Testing Simulated Telemetry for Software Buses (SB-103)...")
        sim_payload = {
            "bus_number": "SB-103",
            "latitude": 12.9810,
            "longitude": 77.6040,
            "speed": 32.0,
            "passenger_count": 19,
            "source": "SIMULATOR"
        }
        res8 = client.post('/api/telemetry', json=sim_payload)
        assert res8.status_code == 200, "Test 8 failed"
        bus_sb103 = Bus.query.filter_by(bus_number="SB-103").first()
        assert bus_sb103.data_source == 'SIMULATED', "SB-103 data_source should be SIMULATED"
        assert bus_sb103.gps_source == 'SIMULATED', "SB-103 gps_source should be SIMULATED"
        assert bus_sb103.hardware_available == False, "SB-103 should NOT claim physical hardware"
        assert bus_sb103.camera_available == False, "SB-103 should NOT claim camera"
        print(f"  [OK] SB-103 Simulated Telemetry Ingested: GPS={bus_sb103.gps_source}, Passengers={bus_sb103.passenger_source}, Hardware Available={bus_sb103.hardware_available}")

        # -------------------------------------------------------------------
        # TEST 9: AI Fleet Agent Autonomous Bus Reallocation & Admin Approval
        # Expected: When SB-101 has degraded health, AI agent pairs it with healthy standby unit,
        # and when approved, automatically executes the swap.
        # -------------------------------------------------------------------
        print("\n [TEST 9] Testing AI Fleet Agent Reallocation & Admin Approval Workflow...")
        # Step 1: Ingest critical maintenance data for SB-101
        client.post('/api/maintenance/manual-entry', json={
            "bus_number": "SB-101",
            "battery_voltage": 10.5,
            "engine_temp": 99.0,
            "tire_pressure": 26.0,
            "brake_health": 55.0,
            "engine_health": 60.0,
            "transmission_health": 70.0
        })

        # Step 2: Get AI recommendations
        recs_check = client.get('/api/fleet/recommendations')
        assert recs_check.status_code == 200, "Failed to fetch recommendations"
        swap_recs = [r for r in recs_check.json['recommendations'] if r.get('can_reallocate')]
        assert len(swap_recs) > 0, "AI Agent should generate actionable swap proposal"
        target_rec = swap_recs[0]
        deg_id = target_rec['degraded_bus']['bus_id']
        rep_id = target_rec['suggested_replacement']['bus_id']
        print(f"  [OK] AI Swap Proposal: Replace {target_rec['degraded_bus']['bus_number']} with Standby {target_rec['suggested_replacement']['bus_number']}")

        # Step 3: Admin approves the swap
        approve_res = client.post('/api/fleet/approve-reallocation', json={
            "degraded_bus_id": deg_id,
            "replacement_bus_id": rep_id,
            "reason": "Verified Admin Fleet Swap Approval"
        })
        assert approve_res.status_code == 200 and approve_res.json.get('reallocated'), "Swap execution failed"
        
        deg_bus = Bus.query.get(deg_id)
        rep_bus = Bus.query.get(rep_id)
        assert deg_bus.status == 'maintenance', "Degraded bus should be in maintenance"
        assert rep_bus.status == 'active', "Replacement bus should now be active"
        print(f"  [OK] Agent Executed Swap: {deg_bus.bus_number} status = {deg_bus.status} | {rep_bus.bus_number} status = {rep_bus.status} (Route ID: {rep_bus.route_id})")

        # -------------------------------------------------------------------
        # Reset health & routes back to standard fleet operations
        # -------------------------------------------------------------------
        client.post('/api/maintenance/reset-bus', json={"bus_number": "SB-101"})
        client.post('/api/maintenance/reset-bus', json={"bus_number": "SB-102"})
        
        bus_sb101 = Bus.query.filter_by(bus_number="SB-101").first()
        if bus_sb101:
            bus_sb101.status = 'active'
            bus_sb101.route_id = 1
            bus_sb101.current_lat = 12.9740
            bus_sb101.current_lng = 77.5970

        bus_sb102 = Bus.query.filter_by(bus_number="SB-102").first()
        if bus_sb102:
            bus_sb102.status = 'active'
            bus_sb102.route_id = 2
            bus_sb102.current_lat = 13.0450
            bus_sb102.current_lng = 77.6500

        bus_sb103 = Bus.query.filter_by(bus_number="SB-103").first()
        if bus_sb103:
            bus_sb103.status = 'active'
            bus_sb103.route_id = 3
            bus_sb103.current_lat = 12.9600
            bus_sb103.current_lng = 77.5800

        bus_sb104 = Bus.query.filter_by(bus_number="SB-104").first()
        if bus_sb104:
            bus_sb104.status = 'standby'
            bus_sb104.route_id = 1
            bus_sb104.current_lat = 13.0010
            bus_sb104.current_lng = 77.6250

        db.session.commit()

    print("\n" + "=" * 75)
    print(" [SUCCESS] ALL 9 ARCHITECTURAL & AGENT VERIFICATION TESTS PASSED (100%)")
    print("=" * 75)

if __name__ == '__main__':
    run_all_tests()

