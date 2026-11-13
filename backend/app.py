import os
from pathlib import Path
from flask import Flask, send_from_directory, redirect, jsonify
from flask_cors import CORS
from backend.config import Config
from database.db import db
from backend.sockets import socketio
from simulation.bus_simulator import simulator_engine

def create_app(config_class=Config):
    # Setup static directories
    frontend_dir = Config.BASE_DIR / 'frontend'
    if not frontend_dir.exists():
        frontend_dir = Config.BASE_DIR / 'smart-bus-frontend'
        
    app = Flask(__name__, static_folder=str(frontend_dir))
    app.config.from_object(config_class)

    # Enable Cross-Origin Resource Sharing
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize Extensions
    db.init_app(app)
    socketio.init_app(app)

    # Register API Blueprints
    from backend.blueprints.auth import auth_bp
    from backend.blueprints.bus import bus_bp
    from backend.blueprints.routes import routes_bp
    from backend.blueprints.driver import driver_bp
    from backend.blueprints.telemetry import telemetry_bp
    from backend.blueprints.alerts import alerts_bp
    from backend.blueprints.maintenance import maintenance_bp
    from backend.blueprints.passenger import passenger_bp
    from backend.blueprints.chatbot import chatbot_bp
    from backend.blueprints.simulation import simulation_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(bus_bp, url_prefix='/api')
    app.register_blueprint(routes_bp, url_prefix='/api')
    app.register_blueprint(driver_bp, url_prefix='/api')
    app.register_blueprint(telemetry_bp, url_prefix='/api')
    app.register_blueprint(alerts_bp, url_prefix='/api')
    app.register_blueprint(maintenance_bp, url_prefix='/api')
    app.register_blueprint(passenger_bp, url_prefix='/api')
    app.register_blueprint(chatbot_bp, url_prefix='/api')
    app.register_blueprint(simulation_bp, url_prefix='/api')

    # Serve Frontend Static Pages & Assets
    @app.route('/')
    @app.route('/index.html')
    def root():
        if (frontend_dir / 'index.html').exists():
            return send_from_directory(str(frontend_dir), 'index.html')
        return redirect('/admin/dashboard.html')

    @app.route('/admin/')
    @app.route('/admin/index.html')
    def admin_root():
        return send_from_directory(str(frontend_dir / 'admin'), 'dashboard.html')

    @app.route('/admin/<path:filename>')
    def serve_admin(filename):
        return send_from_directory(str(frontend_dir / 'admin'), filename)

    @app.route('/passenger/')
    @app.route('/passenger/index.html')
    def passenger_root():
        return send_from_directory(str(frontend_dir / 'passenger'), 'index.html')

    @app.route('/passenger/<path:filename>')
    def serve_passenger(filename):
        return send_from_directory(str(frontend_dir / 'passenger'), filename)

    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        return send_from_directory(str(frontend_dir / 'assets'), filename)

    @app.route('/components/<path:filename>')
    def serve_components(filename):
        return send_from_directory(str(frontend_dir / 'components'), filename)

    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '2.0.0',
            'system': 'Smart Bus Management System (ESP32-S3 + AI Agents)',
            'simulation_running': simulator_engine.is_running
        })

    # Auto-initialize DB & Seed if empty
    with app.app_context():
        db.create_all()
        from database.seed import seed_database
        seed_database()

    # Initialize Simulator with app
    simulator_engine.init_app(app)
    if app.config.get('SIMULATION_ENABLED', True):
        simulator_engine.start()

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
