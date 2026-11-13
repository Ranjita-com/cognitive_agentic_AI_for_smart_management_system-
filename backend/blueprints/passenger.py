from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import Bus, Route, Stop, Feedback, RfidCard, User
from agents.passenger_agent import passenger_agent

passenger_bp = Blueprint('passenger_bp', __name__)

@passenger_bp.route('/passenger/search', methods=['GET'])
def search():
    origin = request.args.get('origin', '')
    destination = request.args.get('destination', '')
    results = passenger_agent.search_buses(origin, destination)
    return jsonify({'success': True, 'count': len(results), 'results': results})

@passenger_bp.route('/passenger/nearby-stops', methods=['GET'])
def nearby_stops():
    try:
        lat = float(request.args.get('latitude', 12.9716))
        lng = float(request.args.get('longitude', 77.5946))
        radius = float(request.args.get('radius_km', 4.0))
    except (ValueError, TypeError):
        lat, lng, radius = 12.9716, 77.5946, 4.0
        
    stops = passenger_agent.find_nearby_stops(lat, lng, radius)
    return jsonify({'success': True, 'count': len(stops), 'stops': stops})

@passenger_bp.route('/passenger/bus/<int:bus_id>/tracking', methods=['GET'])
def track_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    eta_data = passenger_agent.calculate_eta(bus.id)
    
    return jsonify({
        'success': True,
        'bus': bus.to_dict(),
        'eta': eta_data,
        'route': bus.route.to_dict(include_stops=True) if bus.route else None
    })

@passenger_bp.route('/passenger/bus/<int:bus_id>/seats', methods=['GET'])
def get_bus_seats(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    capacity = bus.capacity if bus.capacity > 0 else 40
    occupied_count = min(capacity, bus.current_passengers)
    
    # Generate 2D Seating Grid (Rows of 4 seats: 2 left, aisle, 2 right)
    seats = []
    rows = math_rows = (capacity + 3) // 4
    seat_num = 1
    
    for r in range(1, rows + 1):
        for col_code in ['A', 'B', 'C', 'D']:
            if seat_num <= capacity:
                is_occupied = seat_num <= occupied_count
                seat_type = 'WINDOW' if col_code in ('A', 'D') else 'AISLE'
                if seat_num in (1, 2):
                    seat_type = 'PRIORITY / ACCESSIBLE'
                
                seats.append({
                    'seat_number': f'{r}{col_code}',
                    'seat_index': seat_num,
                    'row': r,
                    'column': col_code,
                    'is_occupied': is_occupied,
                    'type': seat_type
                })
                seat_num += 1
                
    return jsonify({
        'success': True,
        'bus_id': bus.id,
        'bus_number': bus.bus_number,
        'capacity': capacity,
        'occupied_seats': occupied_count,
        'available_seats': max(0, capacity - occupied_count),
        'occupancy_rate': round(bus.occupancy_rate, 1),
        'overcrowded': bus.occupancy_rate >= 100.0,
        'seats': seats
    })

@passenger_bp.route('/passenger/timetable', methods=['GET'])
def get_timetable():
    routes = Route.query.filter_by(is_active=True).all()
    timetables = []
    
    for r in routes:
        buses_count = Bus.query.filter_by(route_id=r.id, status='active').count()
        timetables.append({
            'route_id': r.id,
            'route_number': r.route_number,
            'route_name': r.name,
            'origin': r.origin,
            'destination': r.destination,
            'first_bus': '06:00 AM',
            'last_bus': '11:30 PM',
            'frequency_mins': 12 if r.route_number == '101' else (15 if r.route_number == '202' else 20),
            'fare': r.fare,
            'distance_km': r.distance_km,
            'estimated_duration_mins': r.estimated_duration_mins,
            'active_buses_count': buses_count,
            'stops': [rs.stop.name for rs in r.route_stops if rs.stop]
        })
        
    return jsonify({'success': True, 'timetables': timetables})

@passenger_bp.route('/passenger/feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json() or {}
    passenger_name = data.get('passenger_name', 'Anonymous Passenger').strip()
    rating = int(data.get('rating', 5))
    category = data.get('category', 'Punctuality')
    comments = data.get('comments', '').strip()
    bus_id = data.get('bus_id')
    user_id = data.get('user_id')
    
    if not comments:
        return jsonify({'success': False, 'message': 'Feedback comments required.'}), 400
        
    feedback = Feedback(
        user_id=user_id,
        bus_id=bus_id,
        passenger_name=passenger_name if passenger_name else 'Anonymous Passenger',
        rating=rating,
        category=category,
        comments=comments
    )
    db.session.add(feedback)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Thank you! Your feedback has been received.', 'feedback': feedback.to_dict()}), 201

@passenger_bp.route('/passenger/feedbacks', methods=['GET'])
def get_feedbacks():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).limit(30).all()
    return jsonify({'success': True, 'feedbacks': [f.to_dict() for f in feedbacks]})

@passenger_bp.route('/passenger/pass/<card_uid>', methods=['GET'])
def get_pass_details(card_uid):
    card = RfidCard.query.filter_by(card_uid=card_uid).first()
    if not card:
        return jsonify({'success': False, 'message': 'Smart Bus Pass / RFID Card not found.'}), 404
        
    return jsonify({
        'success': True,
        'card': card.to_dict(),
        'user': card.user.to_dict() if card.user else None
    })

@passenger_bp.route('/passenger/pass/recharge', methods=['POST'])
def recharge_pass():
    data = request.get_json() or {}
    card_uid = data.get('card_uid')
    amount = float(data.get('amount', 50.0))
    
    if not card_uid or amount <= 0:
        return jsonify({'success': False, 'message': 'Valid card UID and positive amount required.'}), 400
        
    card = RfidCard.query.filter_by(card_uid=card_uid).first()
    if not card:
        return jsonify({'success': False, 'message': 'Card not found.'}), 404
        
    card.balance += amount
    if card.user:
        card.user.wallet_balance += amount
        
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Successfully recharged ${amount:.2f}! New balance: ${card.balance:.2f}',
        'card': card.to_dict()
    })

@passenger_bp.route('/passenger/book-ticket', methods=['POST'])
def book_ticket():
    import random
    import string
    data = request.get_json() or {}
    
    bus_id = data.get('bus_id', 1)
    passenger_name = data.get('passenger_name', 'Passenger').strip()
    phone = data.get('phone', '+1-555-0100').strip()
    email = data.get('email', 'passenger@example.com').strip()
    selected_seats = data.get('seats', ['1A'])
    if isinstance(selected_seats, str):
        selected_seats = [s.strip() for s in selected_seats.split(',') if s.strip()]
    
    from_stop = data.get('from_stop', 'Central Station')
    to_stop = data.get('to_stop', 'Airport Terminal')
    promo_code = (data.get('promo_code') or '').strip().upper()
    payment_method = data.get('payment_method', 'CARD')
    
    bus = Bus.query.get(bus_id)
    if not bus:
        return jsonify({'success': False, 'message': 'Bus not found.'}), 404
        
    base_fare_per_seat = bus.route.fare if (bus.route and bus.route.fare) else 25.0
    seat_count = len(selected_seats) if selected_seats else 1
    subtotal = base_fare_per_seat * seat_count
    
    discount = 0.0
    if promo_code == 'SMARTBUS40':
        discount = subtotal * 0.40
    elif promo_code == 'STUDENTPASS':
        discount = min(subtotal, 5.0)
    elif promo_code == 'AIRPORT50':
        discount = subtotal * 0.50
        
    final_fare = max(1.0, subtotal - discount)
    
    # Generate unique ticket ID and QR token
    ticket_id = 'TKT-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    qr_payload = f"SMARTBUS|{ticket_id}|BUS-{bus.bus_number}|SEATS-{','.join(selected_seats)}|FARE-${final_fare:.2f}"
    
    # Update bus passenger count if space available
    if bus.current_passengers + seat_count <= bus.capacity:
        bus.current_passengers += seat_count
        db.session.commit()
        
    return jsonify({
        'success': True,
        'message': 'Seat reservation confirmed! Have a pleasant journey.',
        'ticket': {
            'ticket_id': ticket_id,
            'bus_number': bus.bus_number,
            'bus_model': bus.model,
            'passenger_name': passenger_name,
            'phone': phone,
            'email': email,
            'seats': selected_seats,
            'from_stop': from_stop,
            'to_stop': to_stop,
            'seat_count': seat_count,
            'subtotal': round(subtotal, 2),
            'discount': round(discount, 2),
            'total_fare': round(final_fare, 2),
            'promo_applied': promo_code if discount > 0 else None,
            'payment_status': 'PAID_CONFIRMED',
            'payment_method': payment_method,
            'departure_time': 'Today, Within 15 Mins',
            'qr_payload': qr_payload,
            'booking_time': datetime.now(timezone.utc).strftime('%b %d, %Y - %I:%M %p UTC')
        }
    }), 201
