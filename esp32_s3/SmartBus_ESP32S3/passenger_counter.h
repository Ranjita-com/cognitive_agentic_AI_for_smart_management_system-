#ifndef PASSENGER_COUNTER_H
#define PASSENGER_COUNTER_H

#include <Arduino.h>
#include "pins.h"

class PassengerCounter {
public:
    PassengerCounter();
    void begin();
    int getPassengerCount() const;
    int getEntryDelta();
    int getExitDelta();
    void setCapacity(int cap);
    bool isOvercrowded() const;

    // Static ISR handlers
    static void IRAM_ATTR handleEntryISR();
    static void IRAM_ATTR handleExitISR();

private:
    static volatile int _passengerCount;
    static volatile int _entryDelta;
    static volatile int _exitDelta;
    static volatile unsigned long _lastEntryTime;
    static volatile unsigned long _lastExitTime;
    int _capacity;
};

#endif // PASSENGER_COUNTER_H
