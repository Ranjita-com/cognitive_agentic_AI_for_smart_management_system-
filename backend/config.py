import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent



class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.getenv('SECRET_KEY', 'smart-bus-secret-key-super-secure-2026')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'
    
    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Database
    DB_URL = os.getenv('DATABASE_URL', 'sqlite:///database/smart_bus.db')
    if DB_URL.startswith('sqlite:///'):
        db_rel_path = DB_URL.replace('sqlite:///', '')
        db_full_path = BASE_DIR / db_rel_path
        db_full_path.parent.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_full_path.as_posix()}"
    else:
        SQLALCHEMY_DATABASE_URI = DB_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Simulator
    SIMULATION_ENABLED = os.getenv('SIMULATION_ENABLED', 'True').lower() in ('true', '1', 't')
    SIMULATION_INTERVAL = float(os.getenv('SIMULATION_INTERVAL', 2.0))
    SIMULATED_BUS_COUNT = int(os.getenv('SIMULATED_BUS_COUNT', 4))
    
    # Agent Thresholds
    OVERCROWDING_WARN = float(os.getenv('OVERCROWDING_THRESHOLD_WARN', 0.80))
    OVERCROWDING_CRITICAL = float(os.getenv('OVERCROWDING_THRESHOLD_CRITICAL', 1.00))
    SPEED_LIMIT = float(os.getenv('SPEED_LIMIT_KMH', 65.0))
    ENGINE_TEMP_MAX = float(os.getenv('TEMP_LIMIT_HIGH_CELSIUS', 95.0))
    BATTERY_MIN_VOLTAGE = float(os.getenv('BATTERY_VOLTAGE_MIN', 11.4))
    
    # MQTT
    MQTT_BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')
    MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
    MQTT_TELEMETRY_TOPIC = os.getenv('MQTT_TELEMETRY_TOPIC', 'smartbus/esp32/telemetry')
    MQTT_COMMAND_TOPIC = os.getenv('MQTT_COMMAND_TOPIC', 'smartbus/esp32/command')
