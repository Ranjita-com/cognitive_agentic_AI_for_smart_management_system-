#ifndef EMERGENCY_BUTTON_H
#define EMERGENCY_BUTTON_H

#include <Arduino.h>
#include "pins.h"

class EmergencyButton {
public:
    EmergencyButton();
    void begin();
    bool isTriggered() const;
    void reset();
    void setActuators(bool buzzer, bool redLed, bool greenLed);
    void triggerAlarmTone();

    static void IRAM_ATTR handleSosISR();

private:
    static volatile bool _emergencyActive;
    static volatile unsigned long _lastSosTime;
};

#endif // EMERGENCY_BUTTON_H
