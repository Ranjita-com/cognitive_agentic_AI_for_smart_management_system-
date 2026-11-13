from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from agents.passenger_agent import passenger_agent

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

@socketio.on('connect')
def handle_connect():
    print(f"[WebSocket Connected]: Client {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[WebSocket Disconnected]: Client {request.sid}")

@socketio.on('join_bus_room')
def handle_join_bus(data):
    bus_id = data.get('bus_id')
    if bus_id:
        room = f"bus_{bus_id}"
        join_room(room)
        emit('room_joined', {'room': room, 'message': f'Subscribed to updates for Bus #{bus_id}'})

@socketio.on('leave_bus_room')
def handle_leave_bus(data):
    bus_id = data.get('bus_id')
    if bus_id:
        room = f"bus_{bus_id}"
        leave_room(room)
        emit('room_left', {'room': room})

@socketio.on('passenger_chat_message')
def handle_passenger_chat(data):
    message = data.get('message', '')
    user_id = data.get('user_id')
    response = passenger_agent.process_chat_message(message, user_id)
    emit('passenger_chat_reply', response)
