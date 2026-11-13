#ifndef SMART_BUS_CONFIG_H
#define SMART_BUS_CONFIG_H

// ==========================================
// Network & Server Configuration
// ==========================================
#define WIFI_SSID           "Ranjita"
#define WIFI_PASSWORD       "Ranjita@123"

// Flask Backend API Endpoint
#define SERVER_HOST         "10.150.242.168" // Local Flask backend IP
#define SERVER_PORT         5000
#define TELEMETRY_ENDPOINT  "/api/esp32/telemetry"
#define TELEMETRY_INTERVAL_MS 2000 // Send telemetry every 2 seconds

// Bus Identification
#define BUS_NUMBER          "SB-101"
#define DEVICE_MAC          "ESP32_S3_E4:65:B8:10:01"
#define BUS_CAPACITY        6

// ==========================================
// ESP32-S3 Hardware GPIO Pin Mappings
// ==========================================

// 1. GPS Module (NEO-6M / ATGM336H UART - Serial2)
#define GPS_RX_PIN          16 // Connects to GPS TX
#define GPS_TX_PIN          17 // Connects to GPS RX
#define GPS_BAUD_RATE       9600

// 2. Arduino UNO Inter-Controller UART Link (Serial1)
#define UNO_UART_RX_PIN     1  // ESP32 RX from Arduino TX (Pin 1 on Uno, Pin 18 on Mega)
#define UNO_UART_TX_PIN     2  // ESP32 TX to Arduino RX (Pin 0 on Uno, Pin 19 on Mega)
#define UNO_UART_BAUD_RATE  115200

// 3. Dual Optical IR Passenger Counter Sensors
#define IR_ENTRY_PIN        4  // Entry door optical IR sensor (Interrupt)
#define IR_EXIT_PIN         5  // Exit door optical IR sensor (Interrupt)

// 4. Emergency SOS Push Button
#define SOS_BUTTON_PIN      21 // Active LOW with internal pullup

// 5. Sensor Presence Declarations
// Set to false: Physical vehicle health sensors (battery ADC, engine temp, tire pressure)
// are not physically wired; they are managed as Manual/Admin Maintenance Data via the Web UI.
#define HAS_ADC_VOLTAGE_SENSOR  false
#define HAS_TEMP_SENSOR         false
#define DEFAULT_NOMINAL_VOLTAGE 12.60
#define DEFAULT_NOMINAL_TEMP    84.5

// 6. OV3660 / OV2640 Camera Pins (ESP32-S3 Camera Standard)
#define PWDN_GPIO_NUM       -1
#define RESET_GPIO_NUM      -1
#define XCLK_GPIO_NUM       15
#define SIOD_GPIO_NUM       4
#define SIOC_GPIO_NUM       5
#define Y9_GPIO_NUM         16
#define Y8_GPIO_NUM         17
#define Y7_GPIO_NUM         18
#define Y6_GPIO_NUM         12
#define Y5_GPIO_NUM         10
#define Y4_GPIO_NUM         8
#define Y3_GPIO_NUM         9
#define Y2_GPIO_NUM         11
#define VSYNC_GPIO_NUM      6
#define HREF_GPIO_NUM       7
#define PCLK_GPIO_NUM       13

#endif // SMART_BUS_CONFIG_H
