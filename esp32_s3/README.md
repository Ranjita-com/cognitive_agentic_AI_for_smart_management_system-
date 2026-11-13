# ESP32-S3 Smart Bus Hardware Firmware & Wiring Guide

This directory contains the production-ready embedded firmware for the **ESP32-S3** microcontroller operating as the primary IoT hardware controller for the Smart Bus Management System.

---

## 1. Hardware Bill of Materials (BOM)

| Component | Function | Interface / Pins |
|---|---|---|
| **ESP32-S3-WROOM-1 / DevKitC-1** | Main Dual-Core MCU (Wi-Fi + BLE) | 240MHz, 8MB Flash, 2MB PSRAM |
| **NEO-6M / ATGM336H GPS** | Real-time Geolocation, Speed & Altitude | UART2 (RX: GPIO 16, TX: GPIO 17) |
| **Dual IR Optical Sensors** | Passenger Boarding & Alighting Counter | GPIO 4 (Entry), GPIO 5 (Exit) |
| **RC522 RFID Reader** | Bus Stop Markers & Passenger Smart Cards | SPI (SCK: 12, MISO: 13, MOSI: 11, SS: 10, RST: 9) |
| **OV3660 / OV2640 Camera** | Passenger Cabin Surveillance & Density | DVP 8-bit Parallel Interface |
| **Emergency SOS Push Button** | Instant Driver/Passenger Panic Trigger | GPIO 18 (Active LOW, Internal Pullup) |
| **Piezo Active Buzzer** | Overcrowding & Emergency Siren | GPIO 19 (PWM Audio Output) |
| **Dual LEDs (Green & Red)** | Real-time Status / Alert Indicators | GPIO 2 (Green OK), GPIO 15 (Red Alert) |
| **16x2 / 20x4 I2C LCD Display** | Onboard Telemetry & Next Stop Screen | I2C (SDA: GPIO 21, SCL: GPIO 22, 0x27) |
| **Voltage Divider (100kΩ / 22kΩ)** | 12V Bus Battery Voltage Monitoring | ADC1 Ch0 (GPIO 1) |
| **DS18B20 Temperature Sensor** | Engine Compartment Thermal Sensor | OneWire (GPIO 6) |

---

## 2. Complete Pin Mapping Table

```
ESP32-S3 GPIO       Connected Peripheral                  Protocol / Role
-----------------------------------------------------------------------------
GPIO 16 (RX2)   <-- GPS Module TX                         UART (9600 Baud)
GPIO 17 (TX2)   --> GPS Module RX                         UART (9600 Baud)
GPIO 4          <-- Entry IR Sensor (OUT)                 Digital Interrupt (FALLING)
GPIO 5          <-- Exit IR Sensor (OUT)                  Digital Interrupt (FALLING)
GPIO 18         <-- Emergency Push Button                 Digital Interrupt (FALLING)
GPIO 19         --> Piezo Buzzer (+)                      PWM Tone Output
GPIO 2          --> Green Status LED (+)                  Digital Output (Active HIGH)
GPIO 15         --> Red Alert LED (+)                     Digital Output (Active HIGH)
GPIO 21 (SDA)   <-> I2C LCD / OLED Display (SDA)          I2C (0x27 / 0x3C)
GPIO 22 (SCL)   <-> I2C LCD / OLED Display (SCL)          I2C
GPIO 12 (SCK)   --> RC522 RFID Module (SCK)               SPI
GPIO 13 (MISO)  <-- RC522 RFID Module (MISO)              SPI
GPIO 11 (MOSI)  --> RC522 RFID Module (MOSI)              SPI
GPIO 10 (SS)    --> RC522 RFID Module (SDA / CS)          SPI Chip Select
GPIO 9 (RST)    --> RC522 RFID Module (RST)               Digital Reset
GPIO 1 (ADC1)   <-- Battery Voltage Divider Junction      Analog ADC (0-3.3V)
GPIO 6 (IO)     <-> DS18B20 Temp Sensor Data (4.7kΩ pullup) OneWire
3.3V / 5V       <-- Common Power Rails
GND             <-- Common Ground Bus
```

---

## 3. Circuit Schematic & Block Diagram

```
                             +-------------------+
                             | 12V Bus Battery   |
                             +---------+---------+
                                       |
                                [ Voltage Divider ]
                                (100k / 22k Ohm)
                                       |
                                       v
                                    (GPIO 1)
                                       |
+-------------------+        +---------+---------+        +-------------------+
|  NEO-6M GPS (UART)| =====> |                   | <====> |  RC522 RFID (SPI) |
+-------------------+        |                   |        +-------------------+
                             |     ESP32-S3      |
+-------------------+ =====> |    Dual-Core      | =====> | I2C LCD Display   |
| 2x IR Sensors (IN)|        |    Controller     |        +-------------------+
+-------------------+        |                   |
                             |                   | =====> | Buzzer & LEDs     |
+-------------------+ =====> |                   |        +-------------------+
| SOS Button (INT)  |        +---------+---------+
+-------------------+                  |
                                       | Wi-Fi 802.11 b/g/n
                                       v
                         +---------------------------+
                         | Flask + SocketIO Backend  |
                         |  (REST API & AI Agents)   |
                         +---------------------------+
```

---

## 4. Software Dependencies (Arduino IDE / PlatformIO)

Install the following libraries via the Arduino Library Manager:
1. `ArduinoJson` by Benoit Blanchon (v6.21.x or v7.x)
2. `TinyGPS++` by Mikal Hart (v1.0.3+)
3. `MFRC522` by GithubCommunity (v1.4.10+)
4. `LiquidCrystal_I2C` by Frank de Brabander (v1.1.2+)
5. `OneWire` & `DallasTemperature` (for DS18B20 temperature sensor)

---

## 5. Configuration & Flashing Instructions

1. Open `esp32_s3/config.h` in your editor.
2. Update `WIFI_SSID` and `WIFI_PASSWORD` with your local Wi-Fi credentials.
3. Update `SERVER_HOST` with your Flask backend server IP address (e.g. `192.168.1.50`).
4. Select board **"ESP32S3 Dev Module"** in Arduino IDE.
5. Set **Flash Mode: QIO 80MHz**, **PSRAM: OPI PSRAM**, **Upload Speed: 921600**.
6. Connect ESP32-S3 via USB-C cable and click **Upload**.
7. Open Serial Monitor at **115200 Baud** to view initialization telemetry logs.
