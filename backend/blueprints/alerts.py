from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import Alert, Bus
from agents.safety_agent import safety_agent

alerts_bp = Blueprint('alerts_bp', __name__)

@alerts_bp.route('/alerts', methods=['GET'])
def get_alerts():
    status = request.args.get('status')
    severity = request.args.get('severity')
    bus_id = request.args.get('bus_id', type=int)
    limit = request.args.get('limit', default=50, type=int)
    
    query = Alert.query.order_by(Alert.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(severity=severity)
    if bus_id:
        query = query.filter_by(bus_id=bus_id)
        
    alerts = query.limit(limit).all()
    return jsonify({
        'success': True,
        'count': len(alerts),
        'alerts': [a.to_dict() for a in alerts]
    })

@alerts_bp.route('/alerts/sos', methods=['POST'])
def trigger_sos():
    data = request.get_json() or {}
    bus_id = data.get('bus_id')
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    if not bus_id:
        return jsonify({'success': False, 'message': 'Bus ID required.'}), 400
        
    result = safety_agent.trigger_sos(bus_id, lat, lng)
    
    # Broadcast SOS event via WebSockets
    try:
        from backend.sockets import socketio
        socketio.emit('emergency_sos', result)
    except Exception:
        pass
        
    return jsonify(result)

@alerts_bp.route('/alerts/<int:alert_id>/resolve', methods=['PUT'])
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    data = request.get_json() or {}
    
    alert.status = 'RESOLVED'
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = data.get('resolved_by', 'Admin')
    
    # If SOS alert, resolve bus emergency status
    if alert.alert_type == 'SOS' and alert.bus:
        alert.bus.emergency_status = False
        alert.bus.status = 'active'
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Alert resolved.', 'alert': alert.to_dict()})

@alerts_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['PUT'])
def acknowledge_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = 'ACKNOWLEDGED'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Alert acknowledged.', 'alert': alert.to_dict()})

@alerts_bp.route('/alerts/broadcast', methods=['POST'])
def send_broadcast():
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    severity = data.get('severity', 'INFO').upper()
    alert_type = data.get('alert_type', 'BROADCAST').upper()
    bus_id = data.get('bus_id')

    if not message:
        return jsonify({'success': False, 'message': 'Broadcast message content cannot be empty.'}), 400

    if severity not in ['INFO', 'WARNING', 'CRITICAL', 'HIGH']:
        severity = 'INFO'

    alert = Alert(
        bus_id=bus_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        status='ACTIVE'
    )
    db.session.add(alert)
    db.session.commit()

    alert_dict = alert.to_dict()

    # Real-time WebSocket emission to all passenger & admin clients
    try:
        from backend.sockets import socketio
        socketio.emit('new_alert', {'alert': alert_dict})
        socketio.emit('broadcast_alert', {'alert': alert_dict})
    except Exception as e:
        print(f"[WebSocket Error] Failed to emit broadcast alert: {e}")

    return jsonify({
        'success': True,
        'message': 'Broadcast alert dispatched successfully to all passenger apps and fleet terminals.',
        'alert': alert_dict
    }), 201

@alerts_bp.route('/alerts/active-sos', methods=['GET'])
def get_active_sos():
    active_sos = Alert.query.filter_by(alert_type='SOS', status='ACTIVE').all()
    return jsonify({
        'success': True,
        'count': len(active_sos),
        'alerts': [a.to_dict() for a in active_sos]
    })
