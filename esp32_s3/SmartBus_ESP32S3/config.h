#ifndef CONFIG_H
#define CONFIG_H

#include "pins.h"

// ==========================================
// Network & Telemetry Configuration
// ==========================================
#define WIFI_SSID               "Ranjita"
#define WIFI_PASSWORD           "Ranjita@123"

#define SERVER_HOST             "10.150.242.168"  // Flask Backend Server IP
#define SERVER_PORT             5000
#define TELEMETRY_ENDPOINT      "/api/esp32/telemetry"
#define TELEMETRY_INTERVAL_MS   2000

// Bus Identity Constants
#define BUS_NUMBER              "SB-101"
#define DEVICE_MAC              "ESP32_S3_E4:65:B8:10:01"
#define BUS_CAPACITY            6

// Hardware Parameters
#define GPS_BAUD_RATE           9600
#define LCD_I2C_ADDRESS         0x27
#define LCD_COLS                16
#define LCD_ROWS                2

// Calibration
#define VOLTAGE_DIVIDER_RATIO   5.545
#define ADC_REF_VOLTAGE         3.30
#define ADC_RESOLUTION          4095.0

#endif // CONFIG_H
