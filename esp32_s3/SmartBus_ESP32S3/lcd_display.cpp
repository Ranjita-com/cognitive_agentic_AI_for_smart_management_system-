#include "lcd_display.h"

LCDDisplay::LCDDisplay(uint8_t addr, uint8_t cols, uint8_t rows) : _lcd(addr, cols, rows) {}

void LCDDisplay::begin() {
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    _lcd.init();
    _lcd.backlight();
    _lcd.clear();
}

void LCDDisplay::showBootScreen(const String& busNumber) {
    _lcd.clear();
    _lcd.setCursor(0, 0);
    _lcd.print("SMART BUS " + busNumber);
    _lcd.setCursor(0, 1);
    _lcd.print("Init Sensors...");
}

void LCDDisplay::showTelemetry(const String& busNumber, int passengers, int capacity, float speed, float voltage) {
    _lcd.clear();
    // Line 0: Bus Number & Passenger Occupancy
    _lcd.setCursor(0, 0);
    _lcd.print(busNumber);
    _lcd.print(" P:");
    _lcd.print(passengers);
    _lcd.print("/");
    _lcd.print(capacity);

    // Line 1: Speed & Battery
    _lcd.setCursor(0, 1);
    _lcd.print("Spd:");
    _lcd.print((int)speed);
    _lcd.print("kmh ");
    _lcd.print(voltage, 1);
    _lcd.print("V");
}

void LCDDisplay::showEmergency() {
    _lcd.clear();
    _lcd.setCursor(0, 0);
    _lcd.print("! EMERGENCY SOS !");
    _lcd.setCursor(0, 1);
    _lcd.print("ALERTING FLEET...");
}

void LCDDisplay::showCustomMessage(const String& line1, const String& line2) {
    _lcd.clear();
    _lcd.setCursor(0, 0);
    _lcd.print(line1);
    _lcd.setCursor(0, 1);
    _lcd.print(line2);
}

void LCDDisplay::clear() {
    _lcd.clear();
}
