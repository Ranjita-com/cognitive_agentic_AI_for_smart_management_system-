#ifndef PINS_H
#define PINS_H

// ==========================================
// ESP32-S3 Hardware Pin Mapping Definition
// ==========================================

// 1. GPS Module (NEO-6M / ATGM336H UART2)
#define PIN_GPS_RX           16  // ESP32 RX2 (Connects to GPS TX)
#define PIN_GPS_TX           17  // ESP32 TX2 (Connects to GPS RX)

// 2. Dual Optical IR Passenger Sensors
#define PIN_IR_ENTRY         4   // Optical IR Sensor at Entry Door
#define PIN_IR_EXIT          5   // Optical IR Sensor at Exit Door

// 3. Emergency SOS Push Button
#define PIN_SOS_BUTTON       18  // Active LOW with internal pull-up

// 4. Audio & Visual Actuators
#define PIN_BUZZER           19  // Piezo Active Buzzer
#define PIN_LED_GREEN        2   // System Normal Status LED
#define PIN_LED_RED          15  // Alert / Emergency / Overcrowd LED

// 5. I2C Bus (LCD 16x2 / 20x4 or SSD1306 OLED)
#define PIN_I2C_SDA          21
#define PIN_I2C_SCL          22

// 6. RC522 RFID Reader (SPI Interface)
#define PIN_RFID_SCK         12
#define PIN_RFID_MISO        13
#define PIN_RFID_MOSI        11
#define PIN_RFID_SS          10  // Chip Select (SDA)
#define PIN_RFID_RST         9   // Reset Pin

// 7. Analog Sensors & Battery Divider
#define PIN_BATTERY_ADC      1   // ADC1 Channel 0
#define PIN_TEMP_ONEWIRE     6   // DS18B20 OneWire Bus

#endif // PINS_H
