#ifndef LCD_DISPLAY_H
#define LCD_DISPLAY_H

#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

class LCDDisplay {
public:
    LCDDisplay(uint8_t addr = LCD_I2C_ADDRESS, uint8_t cols = LCD_COLS, uint8_t rows = LCD_ROWS);
    void begin();
    void showBootScreen(const String& busNumber);
    void showTelemetry(const String& busNumber, int passengers, int capacity, float speed, float voltage);
    void showEmergency();
    void showCustomMessage(const String& line1, const String& line2);
    void clear();

private:
    LiquidCrystal_I2C _lcd;
};

#endif // LCD_DISPLAY_H
