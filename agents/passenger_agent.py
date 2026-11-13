from backend.services.passenger_service import passenger_service, PassengerService, haversine_distance

class PassengerAgent:
    """
    Intelligent Passenger Agent responsible for:
    - Accurate dynamic ETA calculations based on real GPS / simulated kinematics, vehicle speed, and stop dwell times.
    - Smart route and bus searching across all buses (real and simulated).
    - Nearby stop discovery with walking distance & time.
    - Natural language transit assistant & AI chatbot.
    """
    
    def __init__(self):
        self.service = passenger_service

    def calculate_eta(self, bus_id, target_stop_id=None):
        return self.service.calculate_eta(bus_id, target_stop_id)

    def search_buses(self, origin_query, destination_query):
        return self.service.search_buses(origin_query, destination_query)

    def find_nearby_stops(self, user_lat, user_lng, max_radius_km=4.0):
        return self.service.find_nearby_stops(user_lat, user_lng, max_radius_km)

    def process_chat_message(self, message_text, user_id=None):
        return self.service.process_chat_message(message_text, user_id)

passenger_agent = PassengerAgent()

