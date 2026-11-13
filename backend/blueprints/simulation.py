from flask import Blueprint, request, jsonify
from simulation.bus_simulator import simulator_engine
from agents.fleet_agent import fleet_agent

simulation_bp = Blueprint('simulation_bp', __name__)

@simulation_bp.route('/simulation/status', methods=['GET'])
def get_simulation_status():
    status = simulator_engine.get_status()
    return jsonify({'success': True, 'simulation': status})

@simulation_bp.route('/simulation/start', methods=['POST'])
def start_simulation():
    simulator_engine.start()
    return jsonify({'success': True, 'message': 'Multi-bus simulation engine started.', 'status': simulator_engine.get_status()})

@simulation_bp.route('/simulation/stop', methods=['POST'])
def stop_simulation():
    simulator_engine.stop()
    return jsonify({'success': True, 'message': 'Multi-bus simulation engine paused.', 'status': simulator_engine.get_status()})

@simulation_bp.route('/simulation/speed', methods=['POST'])
def set_simulation_speed():
    data = request.get_json() or {}
    speed = float(data.get('speed', 1.0))
    simulator_engine.set_speed(speed)
    return jsonify({'success': True, 'message': f'Simulation speed set to {speed}x.', 'speed': speed})

@simulation_bp.route('/simulation/inject-event', methods=['POST'])
def inject_event():
    data = request.get_json() or {}
    bus_id = data.get('bus_id', 1)
    event_type = data.get('event_type', 'PASSENGER_SURGE')
    
    result = simulator_engine.inject_event(bus_id, event_type, data)
    return jsonify(result)

@simulation_bp.route('/fleet/recommendations', methods=['GET'])
def get_recommendations():
    recs = fleet_agent.generate_recommendations()
    return jsonify({'success': True, 'count': len(recs), 'recommendations': recs})

@simulation_bp.route('/fleet/approve-reallocation', methods=['POST'])
def approve_fleet_reallocation():
    from models.db_models import Bus
    data = request.get_json() or {}
    degraded_bus_id = data.get('degraded_bus_id') or data.get('bus_id')
    replacement_bus_id = data.get('replacement_bus_id')
    reason = data.get('reason', 'Admin Approved Automated Fleet Reallocation')

    if not degraded_bus_id:
        return jsonify({'success': False, 'message': 'degraded_bus_id is required.'}), 400

    degraded_bus = Bus.query.get(degraded_bus_id)
    if not degraded_bus:
        return jsonify({'success': False, 'message': f'Bus ID {degraded_bus_id} not found.'}), 404

    result = fleet_agent.auto_reallocate_degraded_bus(
        degraded_bus,
        reason=reason,
        trigger_source="ADMIN_APPROVAL",
        replacement_bus_id=replacement_bus_id
    )
    return jsonify(result)

