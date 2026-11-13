import json
from datetime import datetime, timezone
from database.db import db
from models.db_models import Bus, Alert, MaintenanceRecord, TelemetryLog, MaintenanceAssessment
from models.ml_maintenance import maintenance_ml_model

class MaintenanceService:
    """
    Intelligent Vehicle Health & Maintenance Service.
    Evaluates manually entered and simulated vehicle maintenance data.
    Provides clear separation between Rule-Based Maintenance Priority and ML Predictive Degradation.
    """

    def __init__(self, min_battery=11.4, max_temp=95.0):
        self.min_battery = min_battery
        self.max_temp = max_temp

    def evaluate_manual_maintenance_input(self, bus_id, battery_voltage=None, engine_temp=None, tire_pressure=None,
                                         brake_health=None, engine_health=None, transmission_health=None, notes=None):
        """
        Ingests admin-entered manual maintenance parameters for any bus.
        Executes rule-based health checks, ML predictive degradation, assigns maintenance priority,
        and triggers fleet optimization review.
        """
        bus = Bus.query.get(bus_id)
        if not bus:
            return {'success': False, 'message': 'Bus not found.'}

        # Update bus attributes with explicit MANUAL source
        if battery_voltage is not None: bus.battery_voltage = float(battery_voltage)
        if engine_temp is not None: bus.engine_temp = float(engine_temp)
        if tire_pressure is not None: bus.tire_pressure = float(tire_pressure)
        if brake_health is not None: bus.brake_health = float(brake_health)
        if engine_health is not None: bus.engine_health = float(engine_health)
        if transmission_health is not None: bus.transmission_health = float(transmission_health)
        if notes: bus.maintenance_notes = str(notes)

        bus.maintenance_source = 'MANUAL'
        bus.updated_at = datetime.now(timezone.utc)

        # 1. Rule-Based Evaluation
        rule_findings = []
        rule_priority = 'NORMAL'
        rule_recommendation = 'KEEP_IN_OPERATION'
        rule_score_penalties = 0.0

        # Battery check
        if bus.battery_voltage < self.min_battery:
            rule_findings.append({
                'type': 'CRITICAL_LOW_BATTERY',
                'severity': 'CRITICAL',
                'message': f'Critical low battery voltage: {bus.battery_voltage:.2f}V (Threshold: {self.min_battery:.1f}V). Alternator/Battery check needed.'
            })
            rule_score_penalties += 30.0
            rule_priority = 'CRITICAL'
            rule_recommendation = 'CRITICAL_MAINTENANCE'
        elif bus.battery_voltage < 12.1:
            rule_findings.append({
                'type': 'LOW_BATTERY_WARNING',
                'severity': 'WARNING',
                'message': f'Low battery voltage warning: {bus.battery_voltage:.2f}V (Nominal: 12.6V).'
            })
            rule_score_penalties += 12.0
            if rule_priority == 'NORMAL': rule_priority = 'MONITOR'
            if rule_recommendation == 'KEEP_IN_OPERATION': rule_recommendation = 'MONITOR'

        # Engine Temp check
        if bus.engine_temp > self.max_temp:
            rule_findings.append({
                'type': 'ENGINE_OVERHEAT',
                'severity': 'CRITICAL',
                'message': f'Engine overheating: {bus.engine_temp:.1f}°C (Threshold: {self.max_temp:.1f}°C). Cooling system failure risk.'
            })
            rule_score_penalties += 35.0
            rule_priority = 'CRITICAL'
            rule_recommendation = 'CRITICAL_MAINTENANCE'
        elif bus.engine_temp > 90.0:
            rule_findings.append({
                'type': 'HIGH_TEMP_WARNING',
                'severity': 'WARNING',
                'message': f'High engine temperature: {bus.engine_temp:.1f}°C. Coolant inspection recommended.'
            })
            rule_score_penalties += 15.0
            if rule_priority != 'CRITICAL': rule_priority = 'SERVICE_REQUIRED'
            if rule_recommendation not in ['CRITICAL_MAINTENANCE', 'SERVICE_RECOMMENDED']: rule_recommendation = 'SERVICE_RECOMMENDED'

        # Tire Pressure check
        if bus.tire_pressure < 26.0 or bus.tire_pressure > 38.0:
            rule_findings.append({
                'type': 'HAZARDOUS_TIRE_PRESSURE',
                'severity': 'CRITICAL',
                'message': f'Hazardous tire pressure: {bus.tire_pressure:.1f} PSI (Nominal: 32 PSI).'
            })
            rule_score_penalties += 25.0
            if rule_priority != 'CRITICAL': rule_priority = 'SERVICE_REQUIRED'
            if rule_recommendation not in ['CRITICAL_MAINTENANCE']: rule_recommendation = 'SERVICE_RECOMMENDED'
        elif bus.tire_pressure < 28.0 or bus.tire_pressure > 36.0:
            rule_findings.append({
                'type': 'TIRE_PRESSURE_WARNING',
                'severity': 'WARNING',
                'message': f'Abnormal tire pressure: {bus.tire_pressure:.1f} PSI.'
            })
            rule_score_penalties += 10.0
            if rule_priority == 'NORMAL': rule_priority = 'MONITOR'

        # Component health checks
        if bus.brake_health < 55.0:
            rule_findings.append({
                'type': 'CRITICAL_BRAKE_WEAR',
                'severity': 'CRITICAL',
                'message': f'Severe brake pad wear: {bus.brake_health:.1f}% health remaining. Pad replacement mandatory.'
            })
            rule_score_penalties += 25.0
            rule_priority = 'CRITICAL'
            rule_recommendation = 'CRITICAL_MAINTENANCE'
        elif bus.brake_health < 70.0:
            rule_findings.append({
                'type': 'BRAKE_SERVICE_REQUIRED',
                'severity': 'WARNING',
                'message': f'Brake wear warning: {bus.brake_health:.1f}% health. Service recommended.'
            })
            rule_score_penalties += 10.0
            if rule_priority not in ['CRITICAL', 'SERVICE_REQUIRED']: rule_priority = 'SERVICE_REQUIRED'
            if rule_recommendation not in ['CRITICAL_MAINTENANCE', 'SERVICE_RECOMMENDED']: rule_recommendation = 'SERVICE_RECOMMENDED'

        if bus.engine_health < 60.0:
            rule_findings.append({
                'type': 'ENGINE_HEALTH_WARNING',
                'severity': 'HIGH',
                'message': f'Low engine health: {bus.engine_health:.1f}%. Compression/spark test needed.'
            })
            rule_score_penalties += 20.0
            if rule_priority != 'CRITICAL': rule_priority = 'SERVICE_REQUIRED'
            if rule_recommendation not in ['CRITICAL_MAINTENANCE']: rule_recommendation = 'SERVICE_RECOMMENDED'

        # Compute combined Health Score
        base_component_avg = (bus.brake_health + bus.engine_health + bus.transmission_health) / 3.0
        calculated_health = max(10.0, min(100.0, base_component_avg - rule_score_penalties))
        bus.health_score = calculated_health
        bus.maintenance_priority = rule_priority

        # 2. ML Predictive Degradation (LSTM/Time-Series RUL Forecasting)
        telemetry_sample = [{
            'battery_voltage': bus.battery_voltage,
            'engine_temp': bus.engine_temp,
            'tire_pressure': bus.tire_pressure,
            'speed': bus.speed
        }]
        ml_predictions = maintenance_ml_model.predict_component_health(telemetry_sample)

        # Update MaintenanceRecords in Database
        for p in ml_predictions:
            rec = MaintenanceRecord.query.filter_by(bus_id=bus.id, component=p['component']).first()
            if not rec:
                rec = MaintenanceRecord(
                    bus_id=bus.id,
                    component=p['component'],
                    degradation_score=p['degradation_score'],
                    health_percentage=p['health_percentage'],
                    rul_days=p['rul_days'],
                    status=p['status'],
                    predicted_failure_date=p['predicted_failure_date'],
                    description=p['description']
                )
                db.session.add(rec)
            else:
                rec.degradation_score = p['degradation_score']
                rec.health_percentage = p['health_percentage']
                rec.rul_days = p['rul_days']
                rec.status = p['status']
                rec.predicted_failure_date = p['predicted_failure_date']
                rec.description = p['description']

        # Log MaintenanceAssessment
        assessment = MaintenanceAssessment(
            bus_id=bus.id,
            assessed_by='MANUAL_ADMIN',
            overall_health_score=bus.health_score,
            maintenance_priority=bus.maintenance_priority,
            recommendation=rule_recommendation,
            rule_findings_json=json.dumps(rule_findings),
            ml_predictions_json=json.dumps(ml_predictions),
            status='ACTIVE'
        )
        db.session.add(assessment)

        # Generate Alerts if issues found
        for rf in rule_findings:
            if rf['severity'] in ['CRITICAL', 'HIGH']:
                existing_alert = Alert.query.filter_by(
                    bus_id=bus.id,
                    alert_type=rf['type'],
                    status='ACTIVE'
                ).first()
                if not existing_alert:
                    alert = Alert(
                        bus_id=bus.id,
                        alert_type=rf['type'],
                        severity=rf['severity'],
                        message=f"[{bus.bus_number}] {rf['message']} [Source: Manual Maintenance Entry]",
                        status='ACTIVE',
                        latitude=bus.current_lat,
                        longitude=bus.current_lng
                    )
                    db.session.add(alert)

        db.session.commit()

        # 3. Fleet Agent recommendations will propose standby replacements for Admin approval
        auto_reallocation = None

        # Broadcast via WebSockets
        try:
            from backend.sockets import socketio
            socketio.emit('maintenance_update', {
                'bus': bus.to_dict(),
                'assessment': assessment.to_dict(),
                'rule_findings': rule_findings,
                'ml_predictions': ml_predictions,
                'priority': bus.maintenance_priority,
                'recommendation': rule_recommendation
            })
            socketio.emit('bus_update', {'bus': bus.to_dict()})
        except Exception:
            pass

        return {
            'success': True,
            'bus_number': bus.bus_number,
            'health_score': round(bus.health_score, 1),
            'maintenance_priority': bus.maintenance_priority,
            'recommendation': rule_recommendation,
            'data_source': 'MANUAL',
            'rule_findings': rule_findings,
            'ml_predictions': ml_predictions,
            'auto_reallocation': auto_reallocation
        }

    def get_fleet_priority_ranking(self):
        """
        Ranks all buses in the fleet by maintenance priority and health score.
        Eliminates manual admin inspection work by clearly ordering:
        CRITICAL -> SERVICE_REQUIRED -> MONITOR -> NORMAL.
        """
        buses = Bus.query.all()
        priority_order = {'CRITICAL': 4, 'SERVICE_REQUIRED': 3, 'MONITOR': 2, 'NORMAL': 1}
        
        ranked = sorted(
            buses,
            key=lambda b: (priority_order.get(b.maintenance_priority, 1), 100.0 - b.health_score),
            reverse=True
        )

        return [{
            'bus_id': b.id,
            'bus_number': b.bus_number,
            'status': b.status,
            'route_name': b.route.name if b.route else 'Unassigned',
            'health_score': round(b.health_score, 1),
            'battery_voltage': round(b.battery_voltage, 2),
            'engine_temp': round(b.engine_temp, 1),
            'tire_pressure': round(b.tire_pressure, 1),
            'brake_health': round(b.brake_health, 1),
            'engine_health': round(b.engine_health, 1),
            'maintenance_priority': b.maintenance_priority,
            'maintenance_source': b.maintenance_source,
            'recommendation': 'Critical Workshop Maintenance' if b.maintenance_priority == 'CRITICAL' else ('Service Due' if b.maintenance_priority == 'SERVICE_REQUIRED' else ('Monitor Parameters' if b.maintenance_priority == 'MONITOR' else 'Normal Operation')),
            'hardware_type': 'PHYSICAL_IOT_SB101' if b.bus_number == 'SB-101' else 'SOFTWARE_SIMULATED'
        } for b in ranked]

    def reset_bus_service(self, bus_id):
        """Restores a bus to pristine healthy state and clears active maintenance alerts."""
        bus = Bus.query.get(bus_id)
        if not bus:
            return {'success': False, 'message': 'Bus not found.'}

        bus.battery_voltage = 12.6
        bus.engine_temp = 84.0
        bus.tire_pressure = 32.0
        bus.brake_health = 95.0
        bus.engine_health = 95.0
        bus.transmission_health = 95.0
        bus.health_score = 96.0
        bus.maintenance_priority = 'NORMAL'
        bus.emergency_status = False

        if bus.status == 'maintenance':
            bus.status = 'standby'

        # Reset all component records
        records = MaintenanceRecord.query.filter_by(bus_id=bus.id).all()
        for r in records:
            r.degradation_score = 5.0
            r.health_percentage = 95.0
            r.rul_days = 365
            r.status = 'SERVICED'
            r.last_serviced_date = datetime.now(timezone.utc)
            r.description = f'Serviced on {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.'

        # Resolve active alerts
        active_alerts = Alert.query.filter_by(bus_id=bus.id, status='ACTIVE').all()
        for a in active_alerts:
            a.status = 'RESOLVED'
            a.resolved_at = datetime.now(timezone.utc)
            a.resolved_by = 'DEPOT_ADMIN_SERVICE'

        db.session.commit()
        return {'success': True, 'message': f'Bus {bus.bus_number} restored to nominal depot condition.', 'bus': bus.to_dict()}

    def ingest_manual_maintenance(self, bus_id, data):
        """Helper alias to ingest a dictionary payload for manual maintenance."""
        bus = None
        if isinstance(bus_id, int):
            bus = Bus.query.get(bus_id)
        elif isinstance(bus_id, str):
            bus = Bus.query.filter_by(bus_number=bus_id).first()
        if not bus:
            return {'success': False, 'message': 'Bus not found.'}

        result = self.evaluate_manual_maintenance_input(
            bus_id=bus.id,
            battery_voltage=data.get('battery_voltage'),
            engine_temp=data.get('engine_temp'),
            tire_pressure=data.get('tire_pressure'),
            brake_health=data.get('brake_health'),
            engine_health=data.get('engine_health'),
            transmission_health=data.get('transmission_health'),
            notes=data.get('notes')
        )
        result['bus'] = bus.to_dict()
        result['priority'] = bus.maintenance_priority
        if 'auto_reallocation' in result and result['auto_reallocation']:
            result['reallocation'] = result['auto_reallocation']
        return result

    def calculate_fleet_maintenance_priorities(self):
        """Helper alias for fleet maintenance priority ranking."""
        ranking = self.get_fleet_priority_ranking()
        # Add rank index
        for idx, item in enumerate(ranking, 1):
            item['rank'] = idx
            item['priority_level'] = item['maintenance_priority']
        return ranking

maintenance_service = MaintenanceService()

