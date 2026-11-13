"""
=============================================================================
SMART BUS MANAGEMENT SYSTEM - MASTER RUNNER
=============================================================================
Launches the Flask + SocketIO Backend Server, initializes SQLite Database,
boots up the 4 Autonomous Intelligent Agents (Passenger, Safety, Fleet, Maintenance),
activates the Multi-Bus Simulation Engine for Software Buses, and serves both
the Admin Fleet Dashboard & Passenger Web UI.
=============================================================================
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.app import create_app
from backend.sockets import socketio

def main():
    print("=" * 70)
    print(" SMART BUS MANAGEMENT SYSTEM - STARTING UP...")
    print("=" * 70)
    print(f" [OK] Backend Framework: Flask + Flask-SocketIO (Real-Time WebSockets)")
    print(f" [OK] Database: {Config.DB_URL}")
    print(f" [OK] Real Hardware Bus: SB-101 (ESP32-S3 + Arduino UNO)")
    print(f" [OK] Software Simulated Buses: SB-102, SB-103, SB-104")
    print(f" [OK] ESP32-S3 Hardware Endpoint: http://{Config.HOST}:{Config.PORT}/api/esp32/telemetry")
    print(f" [OK] 4 Intelligent Agents: Passenger, Safety, Fleet, Maintenance")
    print(f" [OK] Simulation Engine: Enabled ({Config.SIMULATED_BUS_COUNT} Software Buses Active)")
    print("-" * 70)
    print(f" [*] Admin Dashboard URL:     http://localhost:{Config.PORT}/admin/dashboard.html")
    print(f" [*] Passenger Mobile App URL: http://localhost:{Config.PORT}/passenger/index.html")
    print("=" * 70)

    app = create_app(Config)
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
