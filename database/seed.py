import json
from datetime import datetime, timezone, timedelta
from database.db import db
from models.db_models import (
    User, Driver, Route, Stop, RouteStop, Bus, 
    RfidCard, MaintenanceRecord, Alert, Feedback, TelemetryLog, PassengerLog
)
from models.ml_maintenance import maintenance_ml_model

def seed_database():
    """Populates the database with initial rich operational data if empty."""
    # Check if data already exists
    if User.query.filter_by(username='admin').first():
        print("Database already contains seed data.")
        return

    print("Seeding Smart Bus database with realistic fleet, routes, and telemetry...")

    # 1. Create Users
    admin_user = User(
        username='admin',
        email='admin@smartbus.io',
        full_name='Fleet Director Alex',
        role='admin',
        phone='+1-800-555-0199',
        wallet_balance=1000.0
    )
    admin_user.set_password('admin123')

    passenger_user = User(
        username='passenger',
        email='passenger@smartbus.io',
        full_name='John Traveler',
        role='passenger',
        phone='+1-555-014-2200',
        rfid_card_id='RFID_PASS_7741',
        wallet_balance=250.0
    )
    passenger_user.set_password('pass123')

    driver_user = User(
        username='driver',
        email='driver@smartbus.io',
        full_name='Michael Vance',
        role='driver',
        phone='+1-555-019-3388',
        wallet_balance=50.0
    )
    driver_user.set_password('driver123')

    db.session.add_all([admin_user, passenger_user, driver_user])
    db.session.commit()

    # 2. Create RFID Cards
    rfid_card1 = RfidCard(
        card_uid='RFID_PASS_7741',
        user_id=passenger_user.id,
        card_holder_name='John Traveler',
        balance=250.0,
        card_type='PASSENGER',
        status='ACTIVE'
    )
    rfid_card2 = RfidCard(
        card_uid='RFID_DRIVER_01',
        user_id=driver_user.id,
        card_holder_name='Michael Vance (Driver)',
        balance=0.0,
        card_type='DRIVER',
        status='ACTIVE'
    )
    db.session.add_all([rfid_card1, rfid_card2])
    db.session.commit()

    # 3. Create Drivers
    drivers_data = [
        Driver(name='Michael Vance', license_number='DL-NY-98214', phone='+1-555-019-3388', email='driver@smartbus.io', experience_years=7, rating=4.9, status='on_duty', total_trips=340, safety_violations=0, avatar='https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150'),
        Driver(name='Sarah Jenkins', license_number='DL-NY-67120', phone='+1-555-019-4411', email='sarah.j@smartbus.io', experience_years=5, rating=4.8, status='on_duty', total_trips=280, safety_violations=0, avatar='https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150'),
        Driver(name='Carlos Rodriguez', license_number='DL-NY-44192', phone='+1-555-019-7722', email='carlos.r@smartbus.io', experience_years=8, rating=4.7, status='on_duty', total_trips=410, safety_violations=1, avatar='https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150'),
        Driver(name='Emily Watson', license_number='DL-NY-33819', phone='+1-555-019-9944', email='emily.w@smartbus.io', experience_years=4, rating=4.9, status='on_duty', total_trips=190, safety_violations=0, avatar='https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150')
    ]
    db.session.add_all(drivers_data)
    db.session.commit()

    # 4. Create Transit Stops (Dedicated Route Waypoints)
    stops_data = [
        # Route 101 Stops: Hospital -> School -> Market -> Bus Terminal
        Stop(name='Hospital Stop', code='ST-101', latitude=12.9716, longitude=77.5946, rfid_tag='RFID_STOP_101', address='Hospital Main Entrance', amenities_json=json.dumps(['Ambulance Bay', 'Wheelchair Ramp', 'Digital ETA Board', 'Shelter'])),
        Stop(name='School Zone', code='ST-102', latitude=12.9819, longitude=77.6052, rfid_tag='RFID_STOP_102', address='City School & Education Hub', amenities_json=json.dumps(['Pedestrian Crossing', 'Shelter', 'Digital ETA Board'])),
        Stop(name='Market Area', code='ST-103', latitude=12.9922, longitude=77.6159, rfid_tag='RFID_STOP_103', address='Central Market Complex', amenities_json=json.dumps(['Shelter', 'Seating', 'Lighting', 'Kiosk'])),
        Stop(name='Bus Terminal', code='ST-104', latitude=13.0010, longitude=77.6250, rfid_tag='RFID_STOP_104', address='Central Bus Terminal Plaza', amenities_json=json.dumps(['Terminal Bays', 'Ticket Counter', 'Restroom', 'ATM', 'WiFi'])),

        # Route 202 Stops: Airport -> Aerospace Tech Park -> Highway Interchange -> Downtown
        Stop(name='Airport Terminal', code='ST-201', latitude=13.0450, longitude=77.6500, rfid_tag='RFID_STOP_201', address='Airport Arrivals Bay 4', amenities_json=json.dumps(['Luggage Assistance', 'Flight Status Screen', 'AC Lounge', 'WiFi'])),
        Stop(name='Aerospace Tech Park', code='ST-202', latitude=13.0280, longitude=77.6380, rfid_tag='RFID_STOP_202', address='Defense & Tech Corridor', amenities_json=json.dumps(['Shelter', 'Seating'])),
        Stop(name='Highway Interchange', code='ST-203', latitude=13.0120, longitude=77.6250, rfid_tag='RFID_STOP_203', address='Expressway Junction 3', amenities_json=json.dumps(['Park & Ride', 'Shelter'])),
        Stop(name='Downtown Financial District', code='ST-204', latitude=12.9780, longitude=77.5900, rfid_tag='RFID_STOP_204', address='Banking Tower Plaza', amenities_json=json.dumps(['Digital ETA Board', 'Shelter', 'Bicycle Lockers'])),

        # Route 303 Stops: University -> Medical College -> Civic Arts -> City Commercial Mall
        Stop(name='University Campus', code='ST-301', latitude=12.9600, longitude=77.5800, rfid_tag='RFID_STOP_301', address='National College Main Road', amenities_json=json.dumps(['Student Help Desk', 'WiFi', 'Shelter'])),
        Stop(name='Medical College', code='ST-302', latitude=12.9650, longitude=77.5880, rfid_tag='RFID_STOP_302', address='Hospital Emergency Entry', amenities_json=json.dumps(['Ambulance Bay', 'Wheelchair Ramp', 'AC Shelter'])),
        Stop(name='Civic Arts Center', code='ST-303', latitude=12.9730, longitude=77.5850, rfid_tag='RFID_STOP_303', address='Museum & Theatre Lane', amenities_json=json.dumps(['Shelter', 'Tourist Kiosk'])),
        Stop(name='South Commercial Mall', code='ST-304', latitude=12.9550, longitude=77.5920, rfid_tag='RFID_STOP_304', address='Grand Mall West Wing', amenities_json=json.dumps(['Underground Parking Transfer', 'Food Court Entry', 'Shelter']))
    ]
    db.session.add_all(stops_data)
    db.session.commit()

    # 5. Create Routes & Polyline Waypoints
    # Route 101 (BS-101 / SB-101): Hospital -> School -> Market -> Bus Terminal
    r101_polyline = [
        [12.9716, 77.5946],
        [12.9789, 77.6022],
        [12.9819, 77.6052],
        [12.9870, 77.6105],
        [12.9922, 77.6159],
        [12.9966, 77.6205],
        [13.0010, 77.6250]
    ]
    route101 = Route(
        route_number='101',
        name='Green Line Express',
        origin='Hospital Stop',
        destination='Bus Terminal',
        distance_km=6.2,
        estimated_duration_mins=15,
        fare=30.0,
        color='#10b981',
        polyline_json=json.dumps(r101_polyline),
        is_active=True
    )

    # Route 202 (BS-102 / SB-102): Airport -> Tech Park -> Highway -> Downtown
    r202_polyline = [
        [13.0450, 77.6500],
        [13.0360, 77.6440],
        [13.0280, 77.6380],
        [13.0200, 77.6310],
        [13.0120, 77.6250],
        [12.9950, 77.6080],
        [12.9780, 77.5900]
    ]
    route202 = Route(
        route_number='202',
        name='Blue Airport Direct',
        origin='Airport Terminal',
        destination='Downtown Financial District',
        distance_km=22.8,
        estimated_duration_mins=45,
        fare=65.0,
        color='#3b82f6',
        polyline_json=json.dumps(r202_polyline),
        is_active=True
    )

    # Route 303 (BS-103 / SB-103): University -> Medical -> Arts -> City Mall
    r303_polyline = [
        [12.9600, 77.5800],
        [12.9625, 77.5840],
        [12.9650, 77.5880],
        [12.9690, 77.5865],
        [12.9730, 77.5850],
        [12.9640, 77.5890],
        [12.9550, 77.5920],
        [12.9600, 77.5800]
    ]
    route303 = Route(
        route_number='303',
        name='Red City Circular',
        origin='University Campus',
        destination='South Commercial Mall',
        distance_km=9.6,
        estimated_duration_mins=24,
        fare=20.0,
        color='#ef4444',
        polyline_json=json.dumps(r303_polyline),
        is_active=True
    )

    db.session.add_all([route101, route202, route303])
    db.session.commit()

    # 6. Assign RouteStops
    st_map = {s.code: s.id for s in Stop.query.all()}
    r101_stops = [
        RouteStop(route_id=route101.id, stop_id=st_map['ST-101'], sequence_order=1, stop_duration_secs=40, distance_from_start_km=0.0, arrival_time_offset_mins=0),
        RouteStop(route_id=route101.id, stop_id=st_map['ST-102'], sequence_order=2, stop_duration_secs=30, distance_from_start_km=2.1, arrival_time_offset_mins=5),
        RouteStop(route_id=route101.id, stop_id=st_map['ST-103'], sequence_order=3, stop_duration_secs=45, distance_from_start_km=4.3, arrival_time_offset_mins=10),
        RouteStop(route_id=route101.id, stop_id=st_map['ST-104'], sequence_order=4, stop_duration_secs=60, distance_from_start_km=6.2, arrival_time_offset_mins=15)
    ]

    r202_stops = [
        RouteStop(route_id=route202.id, stop_id=st_map['ST-201'], sequence_order=1, stop_duration_secs=60, distance_from_start_km=0.0, arrival_time_offset_mins=0),
        RouteStop(route_id=route202.id, stop_id=st_map['ST-202'], sequence_order=2, stop_duration_secs=30, distance_from_start_km=6.4, arrival_time_offset_mins=12),
        RouteStop(route_id=route202.id, stop_id=st_map['ST-203'], sequence_order=3, stop_duration_secs=30, distance_from_start_km=13.0, arrival_time_offset_mins=25),
        RouteStop(route_id=route202.id, stop_id=st_map['ST-204'], sequence_order=4, stop_duration_secs=60, distance_from_start_km=22.8, arrival_time_offset_mins=45)
    ]

    r303_stops = [
        RouteStop(route_id=route303.id, stop_id=st_map['ST-301'], sequence_order=1, stop_duration_secs=30, distance_from_start_km=0.0, arrival_time_offset_mins=0),
        RouteStop(route_id=route303.id, stop_id=st_map['ST-302'], sequence_order=2, stop_duration_secs=40, distance_from_start_km=2.8, arrival_time_offset_mins=6),
        RouteStop(route_id=route303.id, stop_id=st_map['ST-303'], sequence_order=3, stop_duration_secs=30, distance_from_start_km=5.5, arrival_time_offset_mins=13),
        RouteStop(route_id=route303.id, stop_id=st_map['ST-304'], sequence_order=4, stop_duration_secs=40, distance_from_start_km=9.6, arrival_time_offset_mins=24)
    ]
    db.session.add_all(r101_stops + r202_stops + r303_stops)
    db.session.commit()

    # 7. Create Smart Buses
    drivers = Driver.query.all()
    buses_data = [
        # Bus 101: REAL PHYSICAL IoT BUS (ESP32-S3 + OV3660 Camera + GPS + IR Sensors + Arduino UNO + RC522 RFID + LCD + Buzzer + LEDs)
        Bus(
            bus_number='SB-101',
            license_plate='KA-01-EQ-9101',
            model='Volvo 9700 Smart Edition (Physical IoT SB-101)',
            capacity=6,
            current_passengers=0,
            status='active',
            route_id=route101.id,
            driver_id=drivers[0].id,
            current_lat=12.9740,
            current_lng=77.5970,
            speed=38.5,
            heading=45.0,
            altitude=920.0,
            last_stop_id=st_map['ST-101'],
            next_stop_id=st_map['ST-102'],
            emergency_status=False,
            battery_voltage=12.6,
            engine_temp=84.5,
            fuel_level=78.0,
            tire_pressure=32.0,
            brake_health=92.0,
            engine_health=94.0,
            transmission_health=95.0,
            maintenance_notes='Nominal physical depot test bus.',
            maintenance_priority='NORMAL',
            safety_score=98.0,
            health_score=94.0,
            hardware_available=True, # ONLY SB-101 HAS PHYSICAL HARDWARE
            camera_available=True,   # OV3660 Physical Camera Stream
            gps_available=True,
            passenger_sensor_available=True, # Dual IR Sensors
            data_source='REAL',
            gps_source='REAL',
            passenger_source='REAL',
            maintenance_source='MANUAL',
            ir_passenger_count=0,
            yolo_passenger_count=0,
            passenger_reconciliation_strategy='IR_PRIMARY',
            is_simulated=False,
            device_mac='ESP32_S3_E4:65:B8:10:01'
        ),
        # Bus 102: Active Line 202 Fleet Unit (Autonomous Software Simulated on Blue Airport Direct)
        Bus(
            bus_number='SB-102',
            license_plate='KA-01-EQ-9102',
            model='Mercedes Citaro Hybrid (Software Simulated)',
            capacity=40,
            current_passengers=22,
            status='active',
            route_id=route202.id,
            driver_id=drivers[1].id,
            current_lat=13.0450,
            current_lng=77.6500,
            speed=42.0,
            heading=52.0,
            altitude=915.0,
            last_stop_id=st_map['ST-201'],
            next_stop_id=st_map['ST-202'],
            emergency_status=False,
            battery_voltage=12.3,
            engine_temp=89.0,
            fuel_level=62.0,
            tire_pressure=31.5,
            brake_health=78.0,
            engine_health=82.0,
            transmission_health=85.0,
            maintenance_notes='Manual maintenance inspection logged.',
            maintenance_priority='MONITOR',
            safety_score=88.5,
            health_score=90.0,
            hardware_available=False,
            camera_available=False,
            gps_available=True,
            passenger_sensor_available=False,
            data_source='SIMULATED',
            gps_source='SIMULATED',
            passenger_source='SIMULATED',
            maintenance_source='MANUAL',
            ir_passenger_count=0,
            yolo_passenger_count=0,
            passenger_reconciliation_strategy='IR_PRIMARY',
            is_simulated=True,
            device_mac='ESP32_S3_E4:65:B8:10:02'
        ),
        # Bus 103: Active Line 303 Fleet Unit (Autonomous Software Simulated on Red City Circular)
        Bus(
            bus_number='SB-103',
            license_plate='KA-01-EQ-9103',
            model='Volvo 8900 City Cruiser (Software Simulated)',
            capacity=42,
            current_passengers=16,
            status='active',
            route_id=route303.id,
            driver_id=drivers[2].id,
            current_lat=12.9600,
            current_lng=77.5800,
            speed=35.0,
            heading=90.0,
            altitude=920.0,
            last_stop_id=st_map['ST-301'],
            next_stop_id=st_map['ST-302'],
            emergency_status=False,
            battery_voltage=12.75,
            engine_temp=78.0,
            fuel_level=95.0,
            tire_pressure=32.2,
            brake_health=96.0,
            engine_health=98.0,
            transmission_health=97.0,
            maintenance_notes='Fully inspected active line unit.',
            maintenance_priority='NORMAL',
            safety_score=99.5,
            health_score=98.0,
            hardware_available=False,
            camera_available=False,
            gps_available=True,
            passenger_sensor_available=False,
            data_source='SIMULATED',
            gps_source='SIMULATED',
            passenger_source='SIMULATED',
            maintenance_source='MANUAL',
            ir_passenger_count=0,
            yolo_passenger_count=0,
            passenger_reconciliation_strategy='IR_PRIMARY',
            is_simulated=True,
            device_mac='ESP32_S3_E4:65:B8:10:03'
        ),
        # Bus 104: Auxiliary Standby Bus (Software Simulated)
        Bus(
            bus_number='SB-104',
            license_plate='KA-01-EQ-9104',
            model='Scania OmniLink Auxiliary Standby (Software Simulated)',
            capacity=45,
            current_passengers=0,
            status='standby',
            route_id=None,
            driver_id=None,
            current_lat=13.0450,
            current_lng=77.6500,
            speed=0.0,
            heading=0.0,
            altitude=920.0,
            last_stop_id=st_map['ST-201'],
            next_stop_id=None,
            emergency_status=False,
            battery_voltage=12.65,
            engine_temp=79.5,
            fuel_level=90.0,
            tire_pressure=32.0,
            brake_health=94.0,
            engine_health=96.0,
            transmission_health=95.0,
            maintenance_notes='Auxiliary depot backup unit.',
            maintenance_priority='NORMAL',
            safety_score=99.0,
            health_score=96.5,
            hardware_available=False,
            camera_available=False,
            gps_available=True,
            passenger_sensor_available=False,
            data_source='SIMULATED',
            gps_source='SIMULATED',
            passenger_source='SIMULATED',
            maintenance_source='MANUAL',
            ir_passenger_count=0,
            yolo_passenger_count=0,
            passenger_reconciliation_strategy='IR_PRIMARY',
            is_simulated=True,
            device_mac='ESP32_S3_E4:65:B8:10:04'
        )
    ]
    db.session.add_all(buses_data)
    db.session.commit()

    # 8. Create Predictive Maintenance Records for all buses
    for bus in Bus.query.all():
        predictions = maintenance_ml_model._generate_default_predictions()
        for p in predictions:
            record = MaintenanceRecord(
                bus_id=bus.id,
                component=p['component'],
                degradation_score=p['degradation_score'],
                health_percentage=p['health_percentage'],
                rul_days=p['rul_days'],
                status=p['status'],
                predicted_failure_date=p['predicted_failure_date'],
                description=p['description'],
                last_serviced_date=datetime.now(timezone.utc) - timedelta(days=45)
            )
            db.session.add(record)
    db.session.commit()

    # 9. Create Sample Alerts
    buses = Bus.query.all()
    sample_alerts = [
        Alert(
            bus_id=None,
            alert_type='BROADCAST',
            severity='INFO',
            message='Severe rain near Central Station. Reduce speed on Route 101 to 30 km/h.',
            status='ACTIVE',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
        ),
        Alert(
            bus_id=buses[1].id, # SB-102
            alert_type='OVERCROWDING',
            severity='WARNING',
            message='Bus SB-102 occupancy at 85% (34/40 passengers). Approaching peak capacity.',
            status='ACTIVE',
            latitude=buses[1].current_lat,
            longitude=buses[1].current_lng,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=8)
        ),
        Alert(
            bus_id=buses[2].id, # SB-201
            alert_type='INFO',
            severity='INFO',
            message='Bus SB-201 arrived on-time at Aerospace Park Stop.',
            status='RESOLVED',
            latitude=buses[2].current_lat,
            longitude=buses[2].current_lng,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=25),
            resolved_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            resolved_by='SYSTEM_AUTO'
        )
    ]
    db.session.add_all(sample_alerts)

    # 10. Sample Feedbacks
    sample_feedbacks = [
        Feedback(
            user_id=passenger_user.id,
            bus_id=buses[0].id,
            passenger_name='John Traveler',
            rating=5,
            category='Punctuality',
            comments='Bus arrived right on time according to the live ETA countdown. Very clean bus interior!',
            created_at=datetime.now(timezone.utc) - timedelta(hours=3)
        ),
        Feedback(
            user_id=None,
            bus_id=buses[1].id,
            passenger_name='Priya Sharma',
            rating=4,
            category='Comfort',
            comments='AC was great, but bus was slightly crowded during peak office rush hour.',
            created_at=datetime.now(timezone.utc) - timedelta(hours=6)
        )
    ]
    db.session.add_all(sample_feedbacks)
    db.session.commit()

    print("Database successfully seeded with full fleet, routes, stops, and predictive models!")

if __name__ == '__main__':
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_database()
