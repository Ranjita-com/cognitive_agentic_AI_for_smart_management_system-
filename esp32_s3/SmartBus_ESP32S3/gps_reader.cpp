#include "gps_reader.h"

GPSReader::GPSReader() : _serial(2) {
    _data = { 12.9716, 77.5946, 0.0, 920.0, 0.0, 8, false };
}

void GPSReader::begin(unsigned long baud) {
    _serial.begin(baud, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);
    Serial.println("[GPSReader] Initialized on UART2.");
}

void GPSReader::update() {
    while (_serial.available() > 0) {
        if (_gps.encode(_serial.read())) {
            if (_gps.location.isValid()) {
                _data.latitude = _gps.location.lat();
                _data.longitude = _gps.location.lng();
                _data.isValid = true;
            }
            if (_gps.speed.isValid()) {
                _data.speed = _gps.speed.kmph();
            }
            if (_gps.altitude.isValid()) {
                _data.altitude = _gps.altitude.meters();
            }
            if (_gps.course.isValid()) {
                _data.heading = _gps.course.deg();
            }
            if (_gps.satellites.isValid()) {
                _data.satellites = _gps.satellites.value();
            }
        }
    }
}

GPSData GPSReader::getData() const {
    return _data;
}
