import uuid
from flask import Blueprint, request, jsonify
from database.db import db
from models.db_models import ChatMessage
from agents.passenger_agent import passenger_agent

chatbot_bp = Blueprint('chatbot_bp', __name__)

@chatbot_bp.route('/chatbot/message', methods=['POST'])
def send_chat():
    data = request.get_json() or {}
    message_text = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))
    user_id = data.get('user_id')
    
    if not message_text:
        return jsonify({'success': False, 'message': 'Message text cannot be empty.'}), 400
        
    # Log user message
    user_chat = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        sender='USER',
        message=message_text
    )
    db.session.add(user_chat)
    
    # Process with Passenger Agent NLP engine
    response_data = passenger_agent.process_chat_message(message_text, user_id)
    
    # Log AI response
    ai_chat = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        sender='AI',
        message=response_data.get('reply', ''),
        intent=response_data.get('intent'),
        confidence=response_data.get('confidence', 1.0)
    )
    db.session.add(ai_chat)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'reply': response_data.get('reply'),
        'intent': response_data.get('intent'),
        'suggestions': response_data.get('suggestions', []),
        'data': response_data.get('data')
    })

@chatbot_bp.route('/chatbot/history', methods=['GET'])
def get_chat_history():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'success': True, 'messages': []})
        
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    return jsonify({'success': True, 'session_id': session_id, 'messages': [m.to_dict() for m in messages]})
