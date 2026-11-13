import time
import threading
import random
import json
from datetime import datetime, timezone

from simulation.gps_simulator import GPSSimulator
from simulation.passenger_simulator import PassengerSimulator
from simulation.sensor_simulator import SensorSimulator
from simulation.emergency_simulator import EmergencySimulator
from backend.services.telemetry_service import telemetry_service

class MultiBusSimulator:
    """
    Modular Multi-Bus Physics & Telemetry Simulator for Software Buses (SB-102, SB-103, SB-104).
    Guarantees that physical Bus SB-101 is NOT simulated and only software buses receive simulated telemetry.
    """
    
    def __init__(self, app=None):
        self.app = app
        self.is_running = False
        self.simulation_thread = None
        self.tick_interval = 2.0
        self.speed_multiplier = 1.0
        self.current_tick = 0
        self.bus_states = {}

        # Sub-simulators
        self.gps_sim = GPSSimulator()
        self.passenger_sim = PassengerSimulator()
        self.sensor_sim = SensorSimulator()
        self.emergency_sim = EmergencySimulator()

    def init_app(self, app):
        self.app = app

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.simulation_thread = threading.Thread(target=self._run_loop, daemon=True)
            self.simulation_thread.start()
            print("[Simulator] Multi-bus simulation engine started for software buses (SB-102, SB-103, SB-104).")

    def stop(self):
        self.is_running = False
        print("[Simulator] Multi-bus simulation engine stopped.")

    def set_speed(self, speed_factor):
        self.speed_multiplier = max(0.5, min(10.0, float(speed_factor)))

    def get_status(self):
        return {
            'is_running': self.is_running,
            'current_tick': self.current_tick,
            'speed_multiplier': self.speed_multiplier,
            'simulated_buses': len(self.bus_states)
        }

    def _init_bus_states(self):
        with self.app.app_context():
            from models.db_models import Bus
            # Only simulate buses where is_simulated=True and NOT SB-101
            buses = Bus.query.filter(Bus.is_simulated == True, Bus.bus_number != 'SB-101', Bus.status == 'active').all()
            for b in buses:
                polyline = []
                if b.route and b.route.polyline_json:
                    try:
                        polyline = json.loads(b.route.polyline_json)
                    except Exception:
                        polyline = []
                        
                if not polyline:
                    polyline = [[b.current_lat, b.current_lng], [b.current_lat + 0.01, b.current_lng + 0.01]]
                    
                self.bus_states[b.id] = {
                    'bus_id': b.id,
                    'bus_number': b.bus_number,
                    'route_id': b.route_id,
                    'polyline': polyline,
                    'waypoint_idx': 0,
                    'sub_step': 0.0,
                    'dwell_counter': 0,
                    'direction': 1
                }

    def _run_loop(self):
        time.sleep(1.0)
        self._init_bus_states()
        
        while self.is_running:
            try:
                if self.app:
                    with self.app.app_context():
                        self._simulation_tick()
            except Exception as e:
                print(f"[Simulator Error]: {e}")
                
            self.current_tick += 1
            sleep_duration = max(0.2, self.tick_interval / self.speed_multiplier)
            time.sleep(sleep_duration)

    def _simulation_tick(self):
        from database.db import db
        from models.db_models import Bus, RouteStop

        # Filter strictly for software-simulated buses in active state (Never SB-101)
        buses = Bus.query.filter(Bus.is_simulated == True, Bus.bus_number != 'SB-101', Bus.status == 'active').all()
        for bus in buses:
            if not bus.route_id:
                continue

            state = self.bus_states.get(bus.id)
            if not state or state.get('route_id') != bus.route_id or not state.get('polyline'):
                polyline = []
                if bus.route and bus.route.polyline_json:
                    try:
                        polyline = json.loads(bus.route.polyline_json)
                    except Exception:
                        polyline = []
                if not polyline:
                    polyline = [[bus.current_lat, bus.current_lng], [bus.current_lat + 0.01, bus.current_lng + 0.01]]
                state = {
                    'bus_id': bus.id,
                    'bus_number': bus.bus_number,
                    'route_id': bus.route_id,
                    'polyline': polyline,
                    'waypoint_idx': 0,
                    'sub_step': 0.0,
                    'dwell_counter': 0,
                    'direction': 1
                }
                self.bus_states[bus.id] = state

            polyline = state['polyline']
            if len(polyline) < 2:
                continue

            # 1. Handle Dwell Time at Bus Stops
            current_p = bus.current_passengers
            if state['dwell_counter'] > 0:
                state['dwell_counter'] -= 1
                bus.speed = 0.0
                
                if state['dwell_counter'] == 1:
                    new_p, entries, exits = self.passenger_sim.simulate_stop_flux(bus.current_passengers, bus.capacity)
                    current_p = new_p
            else:
                # 2. Advance GPS position using GPSSimulator
                lat, lng, idx, sub_step, direction, spd, heading = self.gps_sim.advance_position(
                    polyline, state['waypoint_idx'], state['sub_step'], state['direction'], self.speed_multiplier
                )
                bus.current_lat = lat
                bus.current_lng = lng
                bus.heading = heading
                bus.speed = spd if not bus.emergency_status else spd + 15.0

                state['waypoint_idx'] = idx
                state['sub_step'] = sub_step
                state['direction'] = direction

                # Random Stop dwell trigger
                if sub_step == 0.0 and random.random() < 0.5:
                    state['dwell_counter'] = 2

            # 3. Simulate Sensors
            sensor_data = self.sensor_sim.update_telemetry(
                bus.battery_voltage, bus.engine_temp, bus.fuel_level, bus.tire_pressure, bus.speed
            )

            # 4. Check Nearest Stop for RFID Tag Simulation
            if bus.route_id:
                route_stops = RouteStop.query.filter_by(route_id=bus.route_id).order_by(RouteStop.sequence_order).all()
                for rs in route_stops:
                    if rs.stop and self.gps_sim.is_near_stop(bus.current_lat, bus.current_lng, rs.stop.latitude, rs.stop.longitude):
                        bus.last_stop_id = rs.stop.id
                        next_seq = (rs.sequence_order % len(route_stops)) + 1
                        for n_rs in route_stops:
                            if n_rs.sequence_order == next_seq:
                                bus.next_stop_id = n_rs.stop.id

            db.session.commit()

            # 5. Process through Telemetry Service with explicit SIMULATED tagging
            telemetry_payload = {
                'bus_id': bus.id,
                'bus_number': bus.bus_number,
                'latitude': bus.current_lat,
                'longitude': bus.current_lng,
                'speed': bus.speed,
                'heading': bus.heading,
                'altitude': bus.altitude,
                'passenger_count': current_p,
                'battery_voltage': sensor_data['battery_voltage'],
                'engine_temp': sensor_data['engine_temp'],
                'tire_pressure': sensor_data['tire_pressure'],
                'fuel_level': sensor_data['fuel_level'],
                'source': 'SIMULATOR'
            }
            telemetry_service.process_telemetry_payload(telemetry_payload)

    def inject_event(self, bus_id, event_type, custom_data=None):
        if not self.app:
            return {'success': False, 'message': 'App not initialized'}
            
        with self.app.app_context():
            from database.db import db
            from models.db_models import Bus
            from agents.safety_agent import safety_agent
            from backend.sockets import socketio

            bus = Bus.query.get(bus_id)
            if not bus:
                return {'success': False, 'message': 'Bus not found'}

            if event_type == 'PASSENGER_SURGE':
                bus.current_passengers, _, _ = self.passenger_sim.trigger_passenger_surge(bus.current_passengers, bus.capacity)
                msg = f'Injected passenger surge into {bus.bus_number} (Current: {bus.current_passengers}/{bus.capacity}).'
            elif event_type == 'SOS_TRIGGER':
                safety_agent.trigger_sos(bus.id)
                msg = f'Injected EMERGENCY SOS on {bus.bus_number}.'
            elif event_type == 'HIGH_ENGINE_TEMP':
                bus.engine_temp = 98.5
                msg = f'Injected engine overheat (98.5°C) on {bus.bus_number}.'
            elif event_type == 'LOW_BATTERY':
                bus.battery_voltage = 11.2
                msg = f'Injected low battery (11.2V) on {bus.bus_number}.'
            elif event_type == 'RESET_NORMAL':
                bus.emergency_status = False
                bus.status = 'active'
                bus.current_passengers = int(bus.capacity * 0.45)
                bus.battery_voltage = 12.6
                bus.engine_temp = 84.0
                msg = f'Reset {bus.bus_number} telemetry to normal nominal values.'
            else:
                msg = f'Unknown event type {event_type}.'

            db.session.commit()
            try:
                socketio.emit('bus_update', {'bus': bus.to_dict()})
            except Exception:
                pass

            return {'success': True, 'message': msg, 'bus': bus.to_dict()}

simulator_engine = MultiBusSimulator()

