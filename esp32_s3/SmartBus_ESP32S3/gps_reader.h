#ifndef GPS_READER_H
#define GPS_READER_H

#include <Arduino.h>
#include <TinyGPS++.h>
#include "pins.h"

struct GPSData {
    double latitude;
    double longitude;
    float speed;
    float altitude;
    float heading;
    int satellites;
    bool isValid;
};

class GPSReader {
public:
    GPSReader();
    void begin(unsigned long baud = 9600);
    void update();
    GPSData getData() const;

private:
    TinyGPSPlus _gps;
    HardwareSerial _serial;
    GPSData _data;
};

#endif // GPS_READER_H
