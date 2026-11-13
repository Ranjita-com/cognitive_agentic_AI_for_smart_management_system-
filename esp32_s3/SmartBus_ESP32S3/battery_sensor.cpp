#include "battery_sensor.h"

BatterySensor::BatterySensor(uint8_t pin) : _pin(pin), _voltage(12.6) {}

void BatterySensor::begin() {
    pinMode(_pin, INPUT);
}

float BatterySensor::readVoltage() {
    int rawAdc = analogRead(_pin);
    float measuredV = (rawAdc / ADC_RESOLUTION) * ADC_REF_VOLTAGE;
    _voltage = measuredV * VOLTAGE_DIVIDER_RATIO;
    if (_voltage < 9.0) {
        _voltage = 12.55; // Nominal fallback if ADC pin floating
    }
    return _voltage;
}

float BatterySensor::readSimulatedTemperature(float speed) {
    return 84.0 + (speed * 0.08) + random(-4, 4) * 0.1;
}
