from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import MaintenanceRecord, Bus, MaintenanceAssessment
from agents.maintenance_agent import maintenance_agent
from backend.services.maintenance_service import maintenance_service

maintenance_bp = Blueprint('maintenance_bp', __name__)

@maintenance_bp.route('/maintenance/overview', methods=['GET'])
def get_maintenance_overview():
    summary = maintenance_agent.get_fleet_maintenance_summary()
    return jsonify({'success': True, 'data': summary})

@maintenance_bp.route('/maintenance/priority-list', methods=['GET'])
def get_priority_list():
    """
    Returns rule-based maintenance priority ranking across all fleet buses
    along with recommended actions (Service, Overhaul, Monitor, Normal).
    """
    priority_data = maintenance_service.calculate_fleet_maintenance_priorities()
    return jsonify({
        'success': True,
        'count': len(priority_data),
        'priorities': priority_data
    })

@maintenance_bp.route('/maintenance/bus/<int:bus_id>', methods=['GET'])
def get_bus_maintenance(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    records = MaintenanceRecord.query.filter_by(bus_id=bus.id).all()
    assessments = MaintenanceAssessment.query.filter_by(bus_id=bus.id).order_by(MaintenanceAssessment.created_at.desc()).limit(10).all()
    
    return jsonify({
        'success': True,
        'bus_id': bus.id,
        'bus_number': bus.bus_number,
        'health_score': bus.health_score,
        'maintenance_status': bus.maintenance_status,
        'maintenance_priority': bus.maintenance_priority,
        'maintenance_source': bus.maintenance_source,
        'battery_voltage': bus.battery_voltage,
        'engine_temp': bus.engine_temp,
        'tire_pressure': bus.tire_pressure,
        'brake_health': bus.brake_health,
        'engine_health': bus.engine_health,
        'transmission_health': bus.transmission_health,
        'maintenance_notes': bus.maintenance_notes,
        'components': [r.to_dict() for r in records],
        'assessments': [a.to_dict() for a in assessments]
    })

@maintenance_bp.route('/maintenance/manual-entry', methods=['POST'])
@maintenance_bp.route('/maintenance/manual-telemetry', methods=['POST'])
@maintenance_bp.route('/maintenance/inspect', methods=['POST'])
def submit_manual_maintenance():
    """
    Endpoint for Admin manual entry of vehicle health data:
    Battery Voltage, Engine Temp, Tire Pressure, Brake Health, Engine Health,
    Transmission Health, and Maintenance Notes.
    Explicitly tags data as MANUAL and triggers rule-based and ML health evaluations.
    """
    data = request.get_json() or {}
    bus_id = data.get('bus_id')
    bus_number = data.get('bus_number')

    bus = None
    if bus_id:
        bus = Bus.query.get(bus_id)
    elif bus_number:
        bus = Bus.query.filter_by(bus_number=bus_number).first()

    if not bus:
        return jsonify({'success': False, 'message': 'Target bus not found.'}), 404

    result = maintenance_service.ingest_manual_maintenance(bus.id, data)
    return jsonify(result)

@maintenance_bp.route('/maintenance/service', methods=['POST'])
def record_service():
    data = request.get_json() or {}
    record_id = data.get('record_id')
    bus_id = data.get('bus_id')
    component = data.get('component')
    
    record = None
    if record_id:
        record = MaintenanceRecord.query.get(record_id)
    elif bus_id and component:
        record = MaintenanceRecord.query.filter_by(bus_id=bus_id, component=component).first()
        
    if not record:
        return jsonify({'success': False, 'message': 'Maintenance record not found.'}), 404
        
    record.degradation_score = 5.0
    record.health_percentage = 95.0
    record.rul_days = 365
    record.status = 'SERVICED'
    record.last_serviced_date = datetime.now(timezone.utc)
    record.description = f'Serviced & inspected on {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.'
    
    if record.bus:
        record.bus.health_score = min(100.0, record.bus.health_score + 10.0)
        record.bus.maintenance_status = 'NORMAL'
        record.bus.maintenance_priority = 'LOW'
        
    db.session.commit()
    return jsonify({'success': True, 'message': f'{record.component} serviced successfully.', 'record': record.to_dict()})

@maintenance_bp.route('/maintenance/reset-bus', methods=['POST'])
def reset_bus_to_healthy():
    """
    Overhauls and resets a bus back to nominal pristine health.
    """
    data = request.get_json() or {}
    bus_id = data.get('bus_id')
    bus_number = data.get('bus_number')
    
    bus = None
    if bus_id:
        bus = Bus.query.get(bus_id)
    elif bus_number:
        bus = Bus.query.filter_by(bus_number=bus_number).first()
        
    if not bus:
        return jsonify({'success': False, 'message': 'Bus not found.'}), 404

    result = maintenance_agent.reset_bus_health(bus.id)
    return jsonify(result)

@maintenance_bp.route('/maintenance/reallocations', methods=['GET'])
def get_reallocations_log():
    from agents.fleet_agent import fleet_agent
    limit = request.args.get('limit', default=20, type=int)
    history = fleet_agent.get_reallocation_history(limit=limit)
    standby_buses = [b.to_dict() for b in fleet_agent.get_standby_buses()]
    return jsonify({
        'success': True,
        'count': len(history),
        'reallocations': history,
        'standby_buses': standby_buses
    })

@maintenance_bp.route('/maintenance/reallocate-manual', methods=['POST'])
def force_reallocate_bus():
    from agents.fleet_agent import fleet_agent
    data = request.get_json() or {}
    bus_id = data.get('bus_id')
    reason = data.get('reason', 'Manual Dispatcher Swap')
    
    bus = Bus.query.get_or_404(bus_id)
    result = fleet_agent.auto_reallocate_degraded_bus(bus, reason=reason, trigger_source="ADMIN_MANUAL")
    return jsonify(result)


