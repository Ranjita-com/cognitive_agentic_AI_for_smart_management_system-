#ifndef BATTERY_SENSOR_H
#define BATTERY_SENSOR_H

#include <Arduino.h>
#include "config.h"

class BatterySensor {
public:
    BatterySensor(uint8_t pin = PIN_BATTERY_ADC);
    void begin();
    float readVoltage();
    float readSimulatedTemperature(float speed);

private:
    uint8_t _pin;
    float _voltage;
};

#endif // BATTERY_SENSOR_H
