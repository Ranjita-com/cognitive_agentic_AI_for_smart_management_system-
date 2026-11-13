from flask import Blueprint, request, jsonify, session
from database.db import db
from models.db_models import User, RfidCard

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required.'}), 400
        
    user = User.query.filter((User.username == username) | (User.email == username)).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid credentials.'}), 401
        
    session['user_id'] = user.id
    session['role'] = user.role
    
    return jsonify({
        'success': True,
        'message': f'Welcome back, {user.full_name}!',
        'user': user.to_dict()
    })

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    full_name = data.get('full_name', '').strip()
    role = data.get('role', 'passenger')
    phone = data.get('phone', '')
    rfid_card_id = data.get('rfid_card_id', '')

    if not username or not email or not password or not full_name:
        return jsonify({'success': False, 'message': 'All required fields must be provided.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists.'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered.'}), 409

    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        phone=phone,
        rfid_card_id=rfid_card_id if rfid_card_id else None,
        wallet_balance=150.0
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    # Link RFID Card if provided
    if rfid_card_id:
        card = RfidCard.query.filter_by(card_uid=rfid_card_id).first()
        if not card:
            card = RfidCard(
                card_uid=rfid_card_id,
                user_id=new_user.id,
                card_holder_name=full_name,
                balance=150.0,
                card_type='PASSENGER',
                status='ACTIVE'
            )
            db.session.add(card)
            db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Registration successful!',
        'user': new_user.to_dict()
    }), 201

@auth_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        # Check query param for fallback
        uid = request.args.get('user_id')
        if uid:
            user = User.query.get(uid)
            if user:
                return jsonify({'success': True, 'user': user.to_dict()})
        return jsonify({'success': False, 'message': 'Not authenticated.'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'}), 404

    return jsonify({'success': True, 'user': user.to_dict()})

@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})
