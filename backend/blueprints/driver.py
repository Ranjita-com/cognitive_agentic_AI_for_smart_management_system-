from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import Driver, Bus, DriverSafetyEvent
from backend.services.camera_service import camera_service

driver_bp = Blueprint('driver_bp', __name__)

@driver_bp.route('/drivers', methods=['GET'])
def get_drivers():
    drivers = Driver.query.all()
    results = []
    for d in drivers:
        d_dict = d.to_dict()
        assigned_bus = Bus.query.filter_by(driver_id=d.id).first()
        d_dict['assigned_bus'] = assigned_bus.bus_number if assigned_bus else 'None'
        d_dict['assigned_bus_id'] = assigned_bus.id if assigned_bus else None
        
        # Attach driver face attentiveness state
        if assigned_bus:
            driver_state = camera_service.driver_states.get(assigned_bus.bus_number, {})
            d_dict['attentiveness_state'] = driver_state.get('attentiveness_state', 'ACTIVE')
            d_dict['ear_score'] = driver_state.get('ear_score', 0.32)
            d_dict['attentiveness_score'] = driver_state.get('attentiveness_score', 96.0)
            d_dict['drowsiness_detected'] = driver_state.get('drowsiness_detected', False)
        else:
            d_dict['attentiveness_state'] = 'OFF_DUTY'
            d_dict['ear_score'] = 0.32
            d_dict['attentiveness_score'] = 100.0
            d_dict['drowsiness_detected'] = False
            
        results.append(d_dict)
    return jsonify({'success': True, 'count': len(results), 'drivers': results})

@driver_bp.route('/drivers/attentiveness-status', methods=['GET'])
def get_attentiveness_status():
    """Returns facial recognition attentiveness status for all drivers across fleet."""
    status_list = camera_service.get_all_driver_attentiveness()
    return jsonify({'success': True, 'count': len(status_list), 'drivers': status_list})

@driver_bp.route('/drivers/inspect-face', methods=['POST'])
def inspect_driver_face():
    """
    On-Demand Face Recognition & Attentiveness Inspection trigger.
    Admin clicks button to recognize driver face and check active vs slightly inactive vs fully inactive state.
    """
    data = request.get_json() or {}
    bus_number = data.get('bus_number', 'SB-101')
    state = data.get('state') # e.g. 'ACTIVE', 'SLIGHTLY_INACTIVE', or 'FULLY_INACTIVE'
    ear = data.get('ear')
    mar = data.get('mar')
    confidence = float(data.get('confidence', 0.94))

    result = camera_service.inspect_driver_face(
        bus_number=bus_number,
        state=state,
        ear=ear,
        mar=mar,
        confidence=confidence
    )
    return jsonify(result)

@driver_bp.route('/drivers', methods=['POST'])
def create_driver():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    license_num = data.get('license_number', '').strip().upper()
    phone = data.get('phone', '').strip()
    
    if not name or not license_num or not phone:
        return jsonify({'success': False, 'message': 'Name, license number, and phone required.'}), 400
        
    driver = Driver(
        name=name,
        license_number=license_num,
        phone=phone,
        email=data.get('email', ''),
        experience_years=int(data.get('experience_years', 3)),
        rating=float(data.get('rating', 4.8)),
        status=data.get('status', 'on_duty')
    )
    db.session.add(driver)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Driver added.', 'driver': driver.to_dict()}), 201

@driver_bp.route('/drivers/<int:driver_id>', methods=['PUT'])
def update_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    data = request.get_json() or {}
    
    if 'status' in data: driver.status = data['status']
    if 'phone' in data: driver.phone = data['phone']
    if 'assigned_bus_id' in data:
        # Reassign bus
        old_buses = Bus.query.filter_by(driver_id=driver.id).all()
        for b in old_buses:
            b.driver_id = None
        if data['assigned_bus_id']:
            new_bus = Bus.query.get(data['assigned_bus_id'])
            if new_bus:
                new_bus.driver_id = driver.id
                
    db.session.commit()
    return jsonify({'success': True, 'message': 'Driver updated.', 'driver': driver.to_dict()})

