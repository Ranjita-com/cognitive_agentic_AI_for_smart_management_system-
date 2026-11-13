import json
from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import Route, Stop, RouteStop

routes_bp = Blueprint('routes_bp', __name__)

@routes_bp.route('/routes', methods=['GET'])
def get_routes():
    include_stops = request.args.get('include_stops', 'true').lower() in ('true', '1')
    routes = Route.query.filter_by(is_active=True).all()
    return jsonify({
        'success': True,
        'count': len(routes),
        'routes': [r.to_dict(include_stops=include_stops) for r in routes]
    })

@routes_bp.route('/routes/<int:route_id>', methods=['GET'])
def get_route(route_id):
    route = Route.query.get_or_404(route_id)
    return jsonify({'success': True, 'route': route.to_dict(include_stops=True)})

@routes_bp.route('/routes', methods=['POST'])
def create_route():
    data = request.get_json() or {}
    route_number = data.get('route_number', '').strip().upper()
    name = data.get('name', '').strip()
    origin = data.get('origin', '').strip()
    destination = data.get('destination', '').strip()
    
    if not route_number or not name:
        return jsonify({'success': False, 'message': 'Route number and name are required.'}), 400
        
    route = Route(
        route_number=route_number,
        name=name,
        origin=origin,
        destination=destination,
        distance_km=float(data.get('distance_km', 10.0)),
        estimated_duration_mins=int(data.get('estimated_duration_mins', 30)),
        fare=float(data.get('fare', 25.0)),
        color=data.get('color', '#3b82f6'),
        polyline_json=json.dumps(data.get('polyline', []))
    )
    db.session.add(route)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Route created.', 'route': route.to_dict(include_stops=True)}), 201

@routes_bp.route('/stops', methods=['GET'])
def get_stops():
    stops = Stop.query.all()
    return jsonify({'success': True, 'count': len(stops), 'stops': [s.to_dict() for s in stops]})

@routes_bp.route('/stops', methods=['POST'])
def create_stop():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip().upper()
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    if not name or not code or lat is None or lng is None:
        return jsonify({'success': False, 'message': 'Name, code, latitude, and longitude are required.'}), 400
        
    stop = Stop(
        name=name,
        code=code,
        latitude=float(lat),
        longitude=float(lng),
        rfid_tag=data.get('rfid_tag'),
        address=data.get('address', ''),
        amenities_json=json.dumps(data.get('amenities', ['Shelter']))
    )
    db.session.add(stop)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Stop created.', 'stop': stop.to_dict()}), 201
