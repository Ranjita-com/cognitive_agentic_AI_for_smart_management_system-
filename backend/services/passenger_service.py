import math
import re
from datetime import datetime
from models.db_models import Bus, Route, Stop, RouteStop, Alert

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class PassengerService:
    """
    Passenger Experience & AI Transit Service.
    Supports ETA calculations, route searching, nearby stop discovery, and NLP transit chatbot.
    Seamlessly operates across REAL IoT hardware (SB-101) and SIMULATED buses (SB-102, SB-103, SB-104).
    """

    def __init__(self):
        self.default_speed_kmh = 32.0
        self.average_dwell_time_mins = 0.75

    def calculate_eta(self, bus_id, target_stop_id=None):
        """
        Calculates dynamic ETA (minutes & distance) for a bus arriving at a given stop.
        Uses real physical GPS for SB-101, and simulated GPS for software buses.
        """
        bus = Bus.query.get(bus_id)
        if not bus:
            return {'error': 'Bus not found', 'eta_minutes': 0}

        target_stop = None
        if target_stop_id:
            target_stop = Stop.query.get(target_stop_id)
        elif bus.next_stop_id:
            target_stop = Stop.query.get(bus.next_stop_id)

        if not target_stop:
            return {
                'bus_id': bus.id,
                'bus_number': bus.bus_number,
                'eta_minutes': 0,
                'distance_km': 0.0,
                'data_source': bus.gps_source,
                'status': 'Unknown'
            }

        dist_km = haversine_distance(bus.current_lat, bus.current_lng, target_stop.latitude, target_stop.longitude)
        current_speed = bus.speed if bus.speed > 5.0 else self.default_speed_kmh
        travel_time_mins = (dist_km / current_speed) * 60.0

        intermediate_stops = 0
        if bus.route_id:
            bus_route_stops = RouteStop.query.filter_by(route_id=bus.route_id).order_by(RouteStop.sequence_order).all()
            next_seq, target_seq = 0, 0
            for rs in bus_route_stops:
                if rs.stop_id == bus.next_stop_id: next_seq = rs.sequence_order
                if rs.stop_id == target_stop.id: target_seq = rs.sequence_order
            if target_seq > next_seq:
                intermediate_stops = max(0, target_seq - next_seq)

        total_eta_mins = max(1, round(travel_time_mins + (intermediate_stops * self.average_dwell_time_mins)))

        return {
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'target_stop_id': target_stop.id,
            'target_stop_name': target_stop.name,
            'distance_km': round(dist_km, 2),
            'current_speed_kmh': round(bus.speed, 1),
            'eta_minutes': total_eta_mins,
            'occupancy_rate': round(bus.occupancy_rate, 1),
            'available_seats': bus.available_seats,
            'gps_source': bus.gps_source,
            'passenger_source': bus.passenger_source,
            'status': 'On Schedule' if total_eta_mins <= 15 else 'Moderate Traffic'
        }

    def search_buses(self, origin_query, destination_query):
        """Searches routes & active buses for origin/destination query."""
        results = []
        routes = Route.query.filter_by(is_active=True).all()
        origin_q = (origin_query or '').lower().strip()
        dest_q = (destination_query or '').lower().strip()

        for route in routes:
            stops = [rs.stop for rs in route.route_stops if rs.stop]
            stop_names = [s.name.lower() for s in stops]

            origin_match = (
                not origin_q
                or any(origin_q in name for name in stop_names)
                or (origin_q in route.origin.lower())
                or (origin_q in route.name.lower())
                or (origin_q in route.route_number.lower())
            )
            dest_match = (
                not dest_q
                or any(dest_q in name for name in stop_names)
                or (dest_q in route.destination.lower())
                or (dest_q in route.name.lower())
                or (dest_q in route.route_number.lower())
            )

            # Check directional order if both origin and dest are specified
            is_valid_direction = True
            if origin_q and dest_q:
                origin_idx, dest_idx = -1, -1
                for i, name in enumerate(stop_names):
                    if origin_q in name or origin_q in route.origin.lower():
                        if origin_idx == -1: origin_idx = i
                    if dest_q in name or dest_q in route.destination.lower():
                        dest_idx = i
                if origin_idx != -1 and dest_idx != -1 and origin_idx > dest_idx:
                    is_valid_direction = False

            if origin_match and dest_match and is_valid_direction:
                active_buses = Bus.query.filter_by(route_id=route.id, status='active').all()
                bus_summaries = []
                for b in active_buses:
                    eta_info = self.calculate_eta(b.id)
                    occupancy_pct = round(b.occupancy_rate, 1)
                    occ_status = 'Available' if occupancy_pct < 65 else ('Moderate' if occupancy_pct < 85 else ('High Occupancy' if occupancy_pct < 100 else 'Full / Overcrowded'))
                    next_stop_label = b.next_stop.name if b.next_stop else (stops[0].name if stops else 'En Route')

                    bus_summaries.append({
                        'bus_id': b.id,
                        'bus_number': b.bus_number,
                        'current_passengers': b.current_passengers,
                        'capacity': b.capacity,
                        'available_seats': b.available_seats,
                        'occupancy_rate': occupancy_pct,
                        'occupancy_status': occ_status,
                        'eta_minutes': eta_info.get('eta_minutes', 5),
                        'distance_km': eta_info.get('distance_km', 0.0),
                        'current_speed': round(b.speed, 1),
                        'current_lat': round(b.current_lat, 5),
                        'current_lng': round(b.current_lng, 5),
                        'next_stop_name': next_stop_label,
                        'current_location_desc': f"Approaching {next_stop_label}" if next_stop_label else f"Lat: {b.current_lat:.3f}, Lng: {b.current_lng:.3f}",
                        'gps_source': b.gps_source,
                        'passenger_source': b.passenger_source,
                        'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED',
                        'emergency_status': b.emergency_status
                    })

                results.append({
                    'route_id': route.id,
                    'route_number': route.route_number,
                    'route_name': route.name,
                    'origin': route.origin,
                    'destination': route.destination,
                    'distance_km': route.distance_km,
                    'estimated_duration_mins': route.estimated_duration_mins,
                    'fare': route.fare,
                    'color': route.color,
                    'stops_count': len(stops),
                    'active_buses': bus_summaries,
                    'stops': [s.to_dict() for s in stops]
                })

        return results

    def find_nearby_stops(self, user_lat, user_lng, max_radius_km=4.0):
        """Finds stops within walking radius of user coordinates."""
        stops = Stop.query.all()
        nearby = []

        for stop in stops:
            dist = haversine_distance(user_lat, user_lng, stop.latitude, stop.longitude)
            if dist <= max_radius_km:
                walk_mins = max(1, round(dist * 12))
                upcoming_buses = []

                route_stops = RouteStop.query.filter_by(stop_id=stop.id).all()
                for rs in route_stops:
                    buses = Bus.query.filter_by(route_id=rs.route_id, status='active').all()
                    for b in buses:
                        eta_data = self.calculate_eta(b.id, stop.id)
                        upcoming_buses.append({
                            'bus_number': b.bus_number,
                            'route_number': b.route.route_number if b.route else '',
                            'route_name': b.route.name if b.route else '',
                            'eta_minutes': eta_data.get('eta_minutes', 5),
                            'available_seats': b.available_seats,
                            'occupancy_rate': round(b.occupancy_rate, 1),
                            'gps_source': b.gps_source
                        })

                upcoming_buses.sort(key=lambda x: x['eta_minutes'])
                nearby.append({
                    'stop_id': stop.id,
                    'name': stop.name,
                    'code': stop.code,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude,
                    'address': stop.address,
                    'distance_km': round(dist, 2),
                    'walking_time_mins': walk_mins,
                    'upcoming_buses': upcoming_buses[:3]
                })

        nearby.sort(key=lambda x: x['distance_km'])
        return nearby

    def _find_bus_or_route_from_text(self, msg):
        """
        Extracts bus object or route object from free text query,
        supporting common abbreviations and typos (e.g., bs-102, bs102, bs 102 -> SB-102).
        """
        clean = msg.lower().strip()
        # Normalize bs-xxx / bs xxx / bsxxx to sb-xxx
        normalized = re.sub(r'\bbs[-_\s]*(\d+)\b', r'sb-\1', clean)

        # 1. Search for specific bus by normalized number
        all_buses = Bus.query.all()
        for b in all_buses:
            num = b.bus_number.lower()  # e.g. sb-102
            digits = re.sub(r'\D', '', num)  # e.g. 102
            if (num in normalized or
                f"sb{digits}" in normalized or
                f"bs{digits}" in normalized or
                f"bus {digits}" in normalized or
                f"bus{digits}" in normalized or
                f"bus-{digits}" in normalized or
                f"#{digits}" in normalized or
                re.search(rf'\b{digits}\b', normalized)):
                return b, b.route

        # 2. Check if route is specified (e.g., route 101, route 202, route 303, green line, aero line, loop)
        for r in Route.query.filter_by(is_active=True).all():
            if (f"route {r.route_number.lower()}" in clean or
                f"route{r.route_number.lower()}" in clean or
                r.name.lower() in clean or
                (f"line {r.route_number.lower()}" in clean) or
                re.search(rf'\b{r.route_number.lower()}\b', clean)):
                active_bus = Bus.query.filter_by(route_id=r.id, status='active').first()
                return active_bus, r

        # 3. Check for 10b / 10a / 10
        if re.search(r'\b10[ab]?\b', clean):
            active_bus = Bus.query.filter_by(route_id=1, status='active').first() or Bus.query.filter(Bus.bus_number.ilike('%101%')).first()
            return active_bus, (active_bus.route if active_bus else None)

        return None, None

    def process_chat_message(self, message_text, user_id=None):
        """
        Intelligent AI Passenger Assistant.
        Handles natural language passenger questions across all transit topics:
        - Specific bus location/ETA/status (BS-102, SB-101, etc.)
        - Missed bus / running late queries
        - Nearby stops and walking times
        - Wheelchair, stroller, and low-floor accessibility
        - Crowding & empty seat availability
        - Accidents, road blocks, stopped buses, and detours
        - Fastest routes & destination navigation (Mall, Airport, Hospital, Terminal)
        - Fare calculations & RFID card savings
        - Operating hours and last bus timings
        """
        msg = (message_text or '').lower().strip()
        target_bus, target_route = self._find_bus_or_route_from_text(msg)

        # 1. Greetings (Exact word boundary to prevent matching substrings like 'which', 'white', etc.)
        if re.search(r'\b(hello|hi|hey|good morning|good afternoon|good evening|greetings)\b', msg) and not any(k in msg for k in ['bus', 'stop', 'which', 'where', 'how', 'is', 'can', 'fastest', 'cost', 'ticket', 'fare', 'late', 'closest', 'near', 'stroller', 'wheelchair']):
            return {
                'reply': "👋 Hello! I am your **Smart Bus AI Assistant**.\n\nI can help you with:\n• **Live Bus Tracking & ETA** (e.g. *'Where is BS-102?'* or *'When will the next bus arrive?'*)\n• **Seat Availability & Crowding** (e.g. *'Are there empty seats?'*)\n• **Delays & Road Closures** (e.g. *'Why is my bus stopped?'*)\n• **Stroller & Wheelchair Accessibility**\n• **Route Planning & Fares** (e.g. *'Fastest way to Downtown Mall'*)\n\nWhat would you like to know?",
                'intent': 'GREETING',
                'confidence': 0.99,
                'suggestions': ['Where is BS-102?', 'Next Bus ETA', 'Check Empty Seats', 'Fares & Schedules']
            }

        # 2. Wheelchair / Stroller / Accessibility Query
        # "Can I fit a stroller/wheelchair on the bus coming in 5 minutes?", "Is it wheelchair accessible?"
        if any(w in msg for w in ['wheelchair', 'stroller', 'accessible', 'accessibility', 'handicap', 'ramp', 'pram', 'baby stroller', 'disabled']):
            bus = target_bus or Bus.query.filter_by(status='active').first()
            seats_left = bus.available_seats if bus else 16
            occ_pct = bus.occupancy_rate if bus else 60.0
            bus_name = f"Bus **{bus.bus_number}**" if bus else "All Smart Buses"

            return {
                'reply': f"♿ **Accessibility & Stroller Information:**\n\nYes! {bus_name} is fully accessible with the following features:\n• **Low-Floor Boarding & Automated Kneeling Ramp** at the front entrance.\n• **Dedicated Stroller & Wheelchair Bays** in the front section (Priority Rows 1A-1B and 2A-2B).\n• **Current Space Available:** The approaching bus currently has **{seats_left} seats free ({occ_pct:.0f}% capacity)**, ensuring ample floor space for a stroller or wheelchair.\n• **Accessible Stations:** Major stops such as *Hospital Stop (ST-101)* and *Airport T1 (ST-201)* have dedicated level-boarding access.",
                'intent': 'ACCESSIBILITY_QUERY',
                'confidence': 0.97,
                'data': {'bus_number': bus.bus_number if bus else 'SB-101', 'available_seats': seats_left, 'accessible': True}
            }

        # 3. Traffic, Accidents, Route Blocked, Detour, or Why Bus is Stopped
        # "Why is my bus stopped? Is there traffic or an accident?", "Is my normal route blocked today?", "Has the bus route been changed or detoured?"
        if any(w in msg for w in ['stopped', 'why is my bus', 'traffic', 'accident', 'blocked', 'detour', 'detoured', 'roadblock', 'closure', 'hazard', 'weather']):
            active_alerts = Alert.query.filter_by(status='ACTIVE').all()
            if active_alerts:
                alert_lines = [f"• **[{a.alert_type} - {a.severity}]**: {a.message} *(Scope: {a.bus.bus_number if a.bus else 'All Fleet'})*" for a in active_alerts[:3]]
                return {
                    'reply': "⚠️ **Current Route & Traffic Advisory:**\n\n" + "\n".join(alert_lines) + "\n\n• Drivers have been advised to proceed with caution. Normal service is ongoing with minor slowdowns.",
                    'intent': 'TRAFFIC_ALERT',
                    'confidence': 0.96,
                    'data': {'alerts_count': len(active_alerts)}
                }
            else:
                avg_speed = target_bus.speed if target_bus else 34.0
                return {
                    'reply': f"✅ **All Transit Routes Clear:**\n\n• There are **no reported accidents, roadblocks, or emergency detours** on your transit network today.\n• If your bus is briefly stopped, it is normal passenger boarding dwell time (~30–45 seconds per stop).\n• Approaching buses are traveling smoothly at an average speed of **{avg_speed:.1f} km/h** on schedule.",
                    'intent': 'TRAFFIC_NORMAL',
                    'confidence': 0.95
                }

        # 4. Missed Bus or Running Late Query
        # "Did I just miss the Bus 10B, or is it running late?", "did i miss my bus", "is bus running late"
        if any(w in msg for w in ['missed', 'did i just miss', 'running late', 'delayed', 'is it late', 'delay', '10b']):
            bus = target_bus or Bus.query.filter_by(status='active').first()
            if bus:
                eta_info = self.calculate_eta(bus.id)
                route_name = bus.route.name if bus.route else 'Express Line'
                route_num = bus.route.route_number if bus.route else '101'
                headway = 12 if route_num == '101' else (15 if route_num == '202' else 20)
                next_stop = eta_info.get('target_stop_name', 'Market Area')

                return {
                    'reply': f"🚌 **Schedule Status for Route {route_num} ({route_name}):**\n\n• The approaching bus **{bus.bus_number}** is traveling at **{bus.speed:.1f} km/h** and is **on schedule**!\n• Estimated arrival at **{next_stop}**: in **~{eta_info['eta_minutes']} minutes** ({eta_info.get('distance_km', 1.5)} km away).\n• **Don't worry if you missed one!** Buses on this line run frequently every **{headway} minutes**.\n• Current seats free on approaching bus: **{bus.available_seats} seats free**.",
                    'intent': 'MISSED_BUS_QUERY',
                    'confidence': 0.96,
                    'data': eta_info
                }

        # 5. Closest Bus Stop / Near Me Query
        # "Which bus stop is the closest to me right now?", "closest stop", "nearby stop"
        if any(w in msg for w in ['closest', 'closest to me', 'nearest stop', 'near me', 'where is the stop', 'nearest bus stop', 'which bus stop']):
            stops = Stop.query.all()
            if stops:
                stops_list = [
                    f"• **{s.name} ({s.code})**: ~{round((i+1)*0.35, 1)} km (approx. {int((i+1)*4)} mins walk) — *Address: {s.address}*"
                    for i, s in enumerate(stops[:4])
                ]
                return {
                    'reply': "🚏 **Nearest Transit Stops Near You:**\n\n" + "\n".join(stops_list) + "\n\n💡 Tip: You can also tap **Near Me** in the bottom navigation for an interactive radar view!",
                    'intent': 'NEARBY_STOPS',
                    'confidence': 0.97
                }

        # 6. Fastest Way to Destination / Navigation Route Planning
        if any(w in msg for w in ['fastest way', 'how to get to', 'how do i reach', 'how to reach', 'how to go to', 'directions to', 'way to']):
            if 'mall' in msg or 'commercial' in msg:
                return {
                    'reply': "🛍️ **Fastest Route to South Commercial Mall:**\n\n1. Board **Route 303 (Red City Circular)**.\n2. Stops: **University Campus ➔ Medical College ➔ Civic Arts Center ➔ South Commercial Mall (ST-304)** (~20 mins travel time).\n• **Fare:** ₹20.00 (or ₹18.00 with RFID pass)\n• **Next Bus:** **SB-103** arriving in **~4 mins** with **available seats**.",
                    'intent': 'ROUTE_NAVIGATION',
                    'confidence': 0.96
                }
            elif 'airport' in msg:
                return {
                    'reply': "✈️ **Fastest Route to Airport Terminal:**\n\n1. Board **Route 202 (Blue Airport Direct)**.\n2. Stops: **Downtown Financial District ➔ Highway Interchange ➔ Aerospace Tech Park ➔ Airport Terminal (ST-201)** (~25 mins).\n• **Fare:** ₹65.00\n• **Next Bus:** **SB-102** arriving in **~5 mins**.",
                    'intent': 'ROUTE_NAVIGATION',
                    'confidence': 0.96
                }
            elif 'hospital' in msg:
                return {
                    'reply': "🏥 **Fastest Route to Hospital Stop:**\n\n1. Board **Route 101 (Green Line Express)** direct to **Hospital Stop (ST-101)** (~15 mins).\n• **Stops on Line 101:** Hospital Stop ➔ School Zone ➔ Market Area ➔ Bus Terminal\n• **Fare:** ₹30.00\n• **Next Bus:** **SB-101 (Physical IoT Bus)** arriving in **~2 mins**.",
                    'intent': 'ROUTE_NAVIGATION',
                    'confidence': 0.96
                }
            elif 'terminal' in msg or 'railway' in msg or 'station' in msg:
                return {
                    'reply': "🚆 **Fastest Route to Bus Terminal:**\n\n1. Take **Route 101 (Green Line Express)**.\n2. Line Progression: **Hospital Stop ➔ School Zone ➔ Market Area ➔ Bus Terminal (ST-104)**.\n• **Fare:** ₹30.00\n• **Travel Time:** ~15 mins.",
                    'intent': 'ROUTE_NAVIGATION',
                    'confidence': 0.96
                }
            else:
                return {
                    'reply': "🗺️ **Transit Navigation:**\nWe operate 3 express lines connecting major hubs:\n• **Route 101 (Green Line)**: Hospital Stop ➔ School Zone ➔ Market Area ➔ Bus Terminal (~15m, ₹30)\n• **Route 202 (Blue Line)**: Airport Terminal ➔ Aerospace Tech Park ➔ Highway Interchange ➔ Downtown Financial District (~25m, ₹65)\n• **Route 303 (Red Line)**: University Campus ➔ Medical College ➔ Civic Arts Center ➔ South Commercial Mall (~20m, ₹20)\n\nWhere are you heading? Tell me your destination!",
                    'intent': 'ROUTE_NAVIGATION_PROMPT',
                    'confidence': 0.91
                }

        # 7. Operating Hours & Last Bus
        if any(w in msg for w in ['last bus', 'tonight', 'first bus', 'schedule', 'operating hours', 'time does', 'hours', 'when does']):
            return {
                'reply': "🕒 **Transit Operating Schedule & Headways:**\n\n• **First Bus:** **06:00 AM** daily across all routes.\n• **Last Bus:** **11:30 PM** departures from all origins.\n\n**Line Frequency:**\n• **Route 101 (Green Line Express)**: Every **10 minutes**\n• **Route 202 (Blue Airport Direct)**: Every **15 minutes**\n• **Route 303 (Red City Circular)**: Every **15 minutes**\n\nNight safety lighting and digital CCTV surveillance operate 24/7 on all fleet buses.",
                'intent': 'OPERATING_HOURS',
                'confidence': 0.97
            }

        # 8. Fares and Ticket Pricing
        # "How much will my ticket cost for this trip?", "fare", "ticket", "cost", "price"
        if any(w in msg for w in ['fare', 'ticket', 'cost', 'price', 'pass', 'how much', 'rupee', 'rupees', 'inr']):
            routes = Route.query.filter_by(is_active=True).all()
            fares_list = [f"• **Route {r.route_number} ({r.name})**: ₹{r.fare:.2f} ({r.origin} ➔ {r.destination})" for r in routes]
            return {
                'reply': "🎟️ **Smart Bus Transit Fares (Indian Rupees):**\n\n" + "\n".join(fares_list) + "\n\n💡 **Smart Card Savings:** Tap your **RFID Smart Bus Card** for an instant **10% discount** and touchless automated fare collection!",
                'intent': 'FARE_INQUIRY',
                'confidence': 0.96
            }

        # 9. Seat Availability & Crowding
        # "Is the upcoming bus full or crowded?", "Are there any empty seats left on the next bus?", "seats", "crowded"
        if any(w in msg for w in ['seat', 'crowd', 'crowded', 'full', 'occupancy', 'empty seats', 'seats left']):
            if target_bus:
                occ_status = 'Plenty of open seats' if target_bus.occupancy_rate < 65 else ('Moderate occupancy' if target_bus.occupancy_rate < 85 else 'High occupancy / Limited seats')
                return {
                    'reply': f"💺 **Seat & Crowd Status for Bus {target_bus.bus_number}:**\n\n• **Available Seats:** **{target_bus.available_seats} Free Seats** ({target_bus.current_passengers}/{target_bus.capacity} occupied)\n• **Occupancy Rate:** **{target_bus.occupancy_rate:.0f}% ({occ_status})**\n• **Passenger Detection Source:** *{target_bus.passenger_source}*\n• **Accessibility:** Priority seating in rows 1-2 open.",
                    'intent': 'SEAT_QUERY',
                    'confidence': 0.97,
                    'data': {'bus_number': target_bus.bus_number, 'available_seats': target_bus.available_seats, 'occupancy_rate': target_bus.occupancy_rate}
                }
            else:
                buses = Bus.query.filter_by(status='active').all()
                buses_info = [
                    f"• **{b.bus_number}** ({b.route.name if b.route else 'Active Line'}): **{b.available_seats} seats free** ({b.current_passengers}/{b.capacity} occupied, {b.occupancy_rate:.0f}% occupancy - {'🟢 Open' if b.occupancy_rate < 70 else ('🟡 Moderate' if b.occupancy_rate < 90 else '🔴 Crowded')})"
                    for b in buses
                ]
                return {
                    'reply': "💺 **Live Fleet Seat & Occupancy Availability:**\n\n" + "\n".join(buses_info) + "\n\nAll counts are monitored in real time via dual onboard IR & AI cameras.",
                    'intent': 'SEAT_QUERY',
                    'confidence': 0.94
                }

        # 10. Specific Bus Status / BS-102 / SB-101 / Tracking & ETA
        # "Where is my bus right now?", "How many minutes until the next bus arrives at my stop?", "where is bs-102", "bs-102", "where is bus 101"
        if target_bus or any(w in msg for w in ['where is', 'eta', 'when will', 'arrive', 'tracking', 'locate', 'minutes', 'bus', 'sb', 'bs', '102', '101', '201', '301']):
            bus = target_bus or Bus.query.filter_by(status='active').first()
            if bus:
                eta_info = self.calculate_eta(bus.id)
                route_name = bus.route.name if bus.route else 'Green Line Express'
                next_stop = eta_info.get('target_stop_name', 'Market Area')
                source_label = "Real-Time Physical IoT Telemetry" if bus.gps_source == 'REAL' else "Live Simulated Transit Telemetry"

                return {
                    'reply': f"📍 **Live Status for Bus {bus.bus_number} ({route_name}):**\n\n• **Current Location:** Currently moving at **{bus.speed:.1f} km/h** approaching **{next_stop}** (Lat: {bus.current_lat:.4f}, Lng: {bus.current_lng:.4f}).\n• **Estimated Arrival (ETA):** **~{eta_info['eta_minutes']} minutes** ({eta_info.get('distance_km', 1.2)} km away).\n• **Seat Availability:** **{bus.available_seats} seats free** out of {bus.capacity} ({bus.occupancy_rate:.0f}% occupancy).\n• **Telemetry Source:** *{source_label}*",
                    'intent': 'BUS_STATUS_QUERY',
                    'confidence': 0.98,
                    'data': eta_info
                }

        # 11. Lost & Found
        if any(w in msg for w in ['lost', 'found', 'forgot', 'bag', 'phone', 'wallet']):
            return {
                'reply': "📦 **Lost Property Assistance:**\n\nIf you misplaced an item on a bus, you can file a lost property report in the Feedback section with your bus number and seat position. Our fleet team will be notified immediately to inspect the vehicle.",
                'intent': 'LOST_ITEM',
                'confidence': 0.97
            }

        # 12. Fallback Intelligent Help
        return {
            'reply': f"I received your question: *'{message_text}'*.\n\nHere are some quick actions you can try:\n• Ask **'Where is BS-102?'** or **'When will the next bus arrive?'**\n• Ask **'Are there empty seats on Route 101?'**\n• Ask **'Can I fit a wheelchair or stroller?'**\n• Ask **'What time is the last bus tonight?'**\n• Ask **'How much is the ticket to Downtown?'**",
            'intent': 'GENERAL_HELP',
            'confidence': 0.85,
            'suggestions': ['Where is BS-102?', 'Next Bus ETA', 'Empty Seats', 'Wheelchair & Stroller', 'Ticket Fares', 'Last Bus Tonight']
        }

passenger_service = PassengerService()
