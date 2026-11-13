#include "passenger_counter.h"
#include "config.h"

volatile int PassengerCounter::_passengerCount = 0;
volatile int PassengerCounter::_entryDelta = 0;
volatile int PassengerCounter::_exitDelta = 0;
volatile unsigned long PassengerCounter::_lastEntryTime = 0;
volatile unsigned long PassengerCounter::_lastExitTime = 0;

PassengerCounter::PassengerCounter() : _capacity(BUS_CAPACITY) {}

void IRAM_ATTR PassengerCounter::handleEntryISR() {
    unsigned long now = millis();
    if (now - _lastEntryTime > 350) { // Debounce 350ms
        _entryDelta++;
        _passengerCount++;
        _lastEntryTime = now;
    }
}

void IRAM_ATTR PassengerCounter::handleExitISR() {
    unsigned long now = millis();
    if (now - _lastExitTime > 350) { // Debounce 350ms
        _exitDelta++;
        if (_passengerCount > 0) {
            _passengerCount--;
        }
        _lastExitTime = now;
    }
}

void PassengerCounter::begin() {
    pinMode(PIN_IR_ENTRY, INPUT_PULLUP);
    pinMode(PIN_IR_EXIT, INPUT_PULLUP);

    attachInterrupt(digitalPinToInterrupt(PIN_IR_ENTRY), handleEntryISR, FALLING);
    attachInterrupt(digitalPinToInterrupt(PIN_IR_EXIT), handleExitISR, FALLING);

    Serial.println("[PassengerCounter] Dual IR interrupts attached.");
}

int PassengerCounter::getPassengerCount() const {
    return _passengerCount;
}

int PassengerCounter::getEntryDelta() {
    int val = _entryDelta;
    _entryDelta = 0;
    return val;
}

int PassengerCounter::getExitDelta() {
    int val = _exitDelta;
    _exitDelta = 0;
    return val;
}

void PassengerCounter::setCapacity(int cap) {
    _capacity = cap;
}

bool PassengerCounter::isOvercrowded() const {
    return _passengerCount >= _capacity;
}
