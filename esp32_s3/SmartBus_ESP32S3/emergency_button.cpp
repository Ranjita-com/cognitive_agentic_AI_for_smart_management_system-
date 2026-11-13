#include "emergency_button.h"

volatile bool EmergencyButton::_emergencyActive = false;
volatile unsigned long EmergencyButton::_lastSosTime = 0;

EmergencyButton::EmergencyButton() {}

void IRAM_ATTR EmergencyButton::handleSosISR() {
    unsigned long now = millis();
    if (now - _lastSosTime > 500) { // 500ms debounce
        _emergencyActive = true;
        _lastSosTime = now;
    }
}

void EmergencyButton::begin() {
    pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);
    pinMode(PIN_BUZZER, OUTPUT);
    pinMode(PIN_LED_GREEN, OUTPUT);
    pinMode(PIN_LED_RED, OUTPUT);

    digitalWrite(PIN_LED_GREEN, HIGH);
    digitalWrite(PIN_LED_RED, LOW);
    digitalWrite(PIN_BUZZER, LOW);

    attachInterrupt(digitalPinToInterrupt(PIN_SOS_BUTTON), handleSosISR, FALLING);
    Serial.println("[EmergencyButton] SOS interrupt attached.");
}

bool EmergencyButton::isTriggered() const {
    return _emergencyActive;
}

void EmergencyButton::reset() {
    _emergencyActive = false;
    setActuators(false, false, true);
}

void EmergencyButton::setActuators(bool buzzer, bool redLed, bool greenLed) {
    digitalWrite(PIN_LED_RED, redLed ? HIGH : LOW);
    digitalWrite(PIN_LED_GREEN, greenLed ? HIGH : LOW);
    if (buzzer) {
        tone(PIN_BUZZER, 1000, 200);
    }
}

void EmergencyButton::triggerAlarmTone() {
    tone(PIN_BUZZER, 1600, 300);
}
