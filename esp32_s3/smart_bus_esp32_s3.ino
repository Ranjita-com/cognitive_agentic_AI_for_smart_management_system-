#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>

// ================= NETWORKING CONFIGURATION =================
// Network 1: Ranjita (Current Active Network)
const char* WIFI_SSID          = "Ranjita";
const char* WIFI_PASSWORD      = "Ranjita@123";
const char* SERVER_URL_RANJITA = "http://10.150.242.168:5000/api/esp32/telemetry";

// Network 2: vivo-1906 (Mobile Hotspot)
const char* ALT_SSID           = "vivo-1906";
const char* ALT_PASSWORD       = "samarth.akkasali";
const char* SERVER_URL_VIVO    = "http://192.168.17.168:5000/api/esp32/telemetry";

// Active dynamic server target (auto-selected based on connected network)
String serverUrl = "http://10.150.242.168:5000/api/esp32/telemetry"; 

// ================= PHYSICAL HARDWARE CAMERA PINS =================
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM     4
#define SIOC_GPIO_NUM     5
#define Y2_GPIO_NUM      11
#define Y3_GPIO_NUM       9
#define Y4_GPIO_NUM       8
#define Y5_GPIO_NUM      10
#define Y6_GPIO_NUM      12
#define Y7_GPIO_NUM      18
#define Y8_GPIO_NUM      17
#define Y9_GPIO_NUM      16
#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM     7
#define PCLK_GPIO_NUM    13

// ================= CAMERA HARDWARE TOGGLE =================
// Set to false if no physical camera module is plugged in
#define ENABLE_CAMERA     false

// ================= ARDUINO INTER-LINK PIN CONFIGURATION =================
// Using the board pin labeled "RX" (GPIO 44 on ESP32-S3)
#ifdef RX
const int HARDWARE_RX_PIN = RX; 
#else
const int HARDWARE_RX_PIN = 44;
#endif

const int CANDIDATE_RX_PINS[] = {HARDWARE_RX_PIN, 44, 1, 16, 2};
const int NUM_CANDIDATE_PINS  = sizeof(CANDIDATE_RX_PINS) / sizeof(CANDIDATE_RX_PINS[0]);
int candidatePinIndex         = 0;
int activeRxPin               = HARDWARE_RX_PIN;
const int DUMMY_TX_PIN        = 42; // Unused pin for UART driver stability

// Web Server and Serial Accumulator
WebServer server(80);
String rxLineBuffer = "";
String lastSeenChars = "";

// Global Variables to hold live telemetry blocks parsed from Arduino Mega/Uno
String parsedPassengerCount = "0";
String parsedCurrentStop    = "Hospital Stop";
String parsedCurrentETA     = "25";
String parsedSOSStatus      = "0";
String parsedLat            = "12.971600";
String parsedLng            = "77.594600";
bool isCameraReady          = false;
bool hasReceivedArduinoData = false;
unsigned long totalRxBytes  = 0;
unsigned long lastPinHunt   = 0;

// ================= LIVE VIDEO STREAM HTML PAGE =================
const char MAIN_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <title>SB-101 Camera Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial; text-align: center; background: #111827; color: white; margin: 0; padding: 20px; }
    h1 { color: #38bdf8; }
    img { width: 90%; max-width: 640px; border: 3px solid #38bdf8; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .btn { padding: 12px 24px; margin: 10px; font-size: 16px; background-color: #0284c7; color: white; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; }
    .btn:hover { background-color: #0369a1; }
  </style>
</head>
<body>
  <h1>🚌 Bus SB-101: Live Camera Feed</h1>
  <p>Connected to Smart Transit Platform @ 5000</p>
  <img src="/stream" alt="Live Camera Stream">
  <br>
  <a href="/capture" target="_blank" class="btn">📷 Capture Frame</a>
</body>
</html>
)rawliteral";

void handleCapture() {
  if (!isCameraReady) {
    server.send(503, "text/plain", "Camera not initialized");
    return;
  }
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void handleStream() {
  if (!isCameraReady) {
    server.send(503, "text/plain", "Camera not initialized");
    return;
  }
  WiFiClient client = server.client();
  client.print(
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
    "Cache-Control: no-cache\r\n"
    "Connection: close\r\n\r\n"
  );

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) break;

    client.printf(
      "--frame\r\n"
      "Content-Type: image/jpeg\r\n"
      "Content-Length: %u\r\n\r\n", fb->len
    );
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);
    delay(10);
  }
}

String parseParameter(String data, String keyword) {
  int index = data.indexOf(keyword);
  if (index == -1) return "";
  int startPos = index + keyword.length();
  int endPos = data.indexOf("&", startPos);
  if (endPos == -1) {
    return data.substring(startPos);
  }
  return data.substring(startPos, endPos);
}

void forwardTelemetryToServer() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);
    http.setReuse(false);

    // Construct telemetry JSON matching backend schema
    String jsonOutput = "{";
    jsonOutput += "\"bus_name\":\"SB-101\",";
    jsonOutput += "\"bus_number\":\"SB-101\",";
    jsonOutput += "\"latitude\":" + parsedLat + ",";
    jsonOutput += "\"longitude\":" + parsedLng + ",";
    jsonOutput += "\"passengers\":" + parsedPassengerCount + ",";
    jsonOutput += "\"stop\":\"" + parsedCurrentStop + "\",";
    jsonOutput += "\"current_stop\":\"" + parsedCurrentStop + "\",";
    jsonOutput += "\"eta\":" + parsedCurrentETA + ",";
    jsonOutput += "\"sos\":" + parsedSOSStatus + ",";
    jsonOutput += "\"active_pin\":" + String(activeRxPin) + ",";
    jsonOutput += "\"pin_signal\":" + String(digitalRead(activeRxPin)) + ",";
    jsonOutput += "\"rx_preview\":\"" + lastSeenChars + "\",";
    jsonOutput += "\"arduino_bytes\":" + String(totalRxBytes);
    jsonOutput += "}";

    int httpResponseCode = http.POST(jsonOutput);
    if (httpResponseCode > 0) {
      Serial.printf("[HTTP Server Link] Telemetry POST Status: %d | Payload: %s\n", httpResponseCode, jsonOutput.c_str());
    } else {
      Serial.printf("[HTTP Server Link] POST failed, error: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  }
}

void setup() {
  // 1. USB debugging to laptop
  Serial.begin(115200); 
  
  // 2. Hardware UART1 listening directly on the pin labeled "RX" (GPIO 44)
  pinMode(activeRxPin, INPUT_PULLUP);
  Serial1.begin(115200, SERIAL_8N1, activeRxPin, DUMMY_TX_PIN); 

  delay(1000);
  Serial.println("\n========================================================");
  Serial.println(" --- ESP32-S3 Smart Bus Telemetry Gateway Active --- ");
  Serial.printf(" [*] Hardware UART1 Listening Directly on Pin 'RX' (GPIO %d)\n", activeRxPin);
  Serial.printf(" [*] Backend Telemetry Target: %s\n", serverUrl.c_str());
  Serial.println("========================================================\n");

  // ================= CAMERA HARDWARE INITIALIZATION =================
  if (ENABLE_CAMERA) {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
      Serial.printf("[Camera] Init failed (0x%x) - Continuing telemetry only\n", err);
      isCameraReady = false;
    } else {
      Serial.println("[Camera] OV3660 Camera initialized successfully.");
      isCameraReady = true;
    }
  } else {
    Serial.println("[Camera] Camera disabled (ENABLE_CAMERA = false) - Running Telemetry Mode");
    isCameraReady = false;
  }

  // ================= WI-FI CONNECTION =================
  WiFi.disconnect(true);
  delay(300);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  Serial.println("\n[WiFi] Scanning nearby 2.4 GHz networks...");
  int n = WiFi.scanNetworks();
  const char* activeSSID = WIFI_SSID;
  const char* activePass = WIFI_PASSWORD;
  bool foundSSID = false;

  if (n == 0) {
    Serial.println("[WiFi] No 2.4 GHz networks detected. Check hotspot frequency band!");
  } else {
    Serial.printf("[WiFi] Found %d networks:\n", n);
    for (int i = 0; i < n; ++i) {
      Serial.printf("   - %s (%d dBm, Ch %d)\n", WiFi.SSID(i).c_str(), WiFi.RSSI(i), WiFi.channel(i));
      if (WiFi.SSID(i) == WIFI_SSID) {
        foundSSID = true;
        activeSSID = WIFI_SSID;
        activePass = WIFI_PASSWORD;
        serverUrl  = SERVER_URL_RANJITA;
      } else if (!foundSSID && WiFi.SSID(i) == ALT_SSID) {
        foundSSID = true;
        activeSSID = ALT_SSID;
        activePass = ALT_PASSWORD;
        serverUrl  = SERVER_URL_VIVO;
      }
    }
  }

  if (foundSSID) {
    Serial.printf("[WiFi] Target network '%s' found in range! Connecting...\n", activeSSID);
  } else {
    Serial.printf("[WiFi] Attempting connection to '%s'...\n", activeSSID);
  }

  WiFi.begin(activeSSID, activePass);
  int retryCount = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retryCount++;
    if (retryCount % 20 == 0) {
      int st = WiFi.status();
      Serial.printf("\n[WiFi] Status: %d (%s) - Trying '%s'...\n", 
                    st, 
                    st == 6 ? "DISCONNECTED - check password / 2.4GHz" : 
                    st == 4 ? "AUTH_FAIL" : 
                    st == 1 ? "SSID_NOT_FOUND" : "CONNECTING", 
                    activeSSID);
      // Re-trigger association if stuck
      WiFi.disconnect();
      delay(300);
      WiFi.begin(activeSSID, activePass);
    }
  }
  Serial.println("\n[WiFi] Connected Successfully!");
  Serial.print("[WiFi] Assigned ESP32 IP: ");
  Serial.println(WiFi.localIP());
  Serial.printf("[WiFi] Active Backend Telemetry Target: %s\n", serverUrl.c_str());

  // ================= WEB SERVER HANDLERS =================
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html", MAIN_PAGE); });
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/stream", HTTP_GET, handleStream);
  server.begin();
}

void handleIncomingByte(char c) {
  // Capture readable characters into rolling debug preview buffer
  if (c >= 32 && c <= 126) {
    lastSeenChars += c;
    if (lastSeenChars.length() > 25) {
      lastSeenChars = lastSeenChars.substring(lastSeenChars.length() - 25);
    }
  }

  if (c == '\n' || c == '\r') {
    rxLineBuffer.trim();
    if (rxLineBuffer.length() > 0) {
      Serial.printf("[Arduino Serial IN] %s\n", rxLineBuffer.c_str());

      int busDataIdx = rxLineBuffer.indexOf("BUS_DATA:");
      if (busDataIdx != -1) {
        String cleanQuery = rxLineBuffer.substring(busDataIdx + 9);

        String countVal = parseParameter(cleanQuery, "Count=");
        String stopVal  = parseParameter(cleanQuery, "Stop=");
        String etaVal   = parseParameter(cleanQuery, "ETA=");
        String sosVal   = parseParameter(cleanQuery, "SOS=");
        String latVal   = parseParameter(cleanQuery, "Lat=");
        String lngVal   = parseParameter(cleanQuery, "Lng=");

        if (countVal.length() > 0) parsedPassengerCount = countVal;
        if (stopVal.length() > 0)  parsedCurrentStop = stopVal;
        if (etaVal.length() > 0)   parsedCurrentETA = etaVal;
        if (sosVal.length() > 0)   parsedSOSStatus = sosVal;
        if (latVal.length() > 0)   parsedLat = latVal;
        if (lngVal.length() > 0)   parsedLng = lngVal;
        if (!hasReceivedArduinoData) {
          Serial.println("\n********************************************************");
          Serial.printf(">>> [SUCCESS] ARDUINO DETECTED & LOCKED ON PIN %d (GPIO %d)! <<<\n", activeRxPin, activeRxPin);
          Serial.println("********************************************************\n");
        }
        hasReceivedArduinoData = true;

        Serial.printf("[Parsed Live Metrics] -> Count: %s | Stop: %s | ETA: %s mins | Lat: %s | Lng: %s | SOS: %s\n",
                      parsedPassengerCount.c_str(), parsedCurrentStop.c_str(),
                      parsedCurrentETA.c_str(), parsedLat.c_str(), parsedLng.c_str(), parsedSOSStatus.c_str());

        // Forward live metrics payload immediately to Flask backend
        forwardTelemetryToServer();
      }
    }
    rxLineBuffer = "";
  } else {
    rxLineBuffer += c;
    if (rxLineBuffer.length() > 250) {
      rxLineBuffer = ""; // Reset buffer if noise overflows
    }
  }
}

void loop() {
  server.handleClient();

  // 1. Read incoming telemetry stream from Arduino Mega
  while (Serial1.available() > 0) {
    totalRxBytes++;
    char c = (char)Serial1.read();
    handleIncomingByte(c);
  }

  // 2. Auto-Pin Hunter: If Arduino signal not locked yet, dwell on each candidate pin for 10s (gives Arduino 5 chances to transmit)
  if (!hasReceivedArduinoData && (millis() - lastPinHunt >= 10000)) {
    lastPinHunt = millis();
    candidatePinIndex = (candidatePinIndex + 1) % NUM_CANDIDATE_PINS;
    activeRxPin = CANDIDATE_RX_PINS[candidatePinIndex];
    
    Serial1.end();
    Serial1.begin(115200, SERIAL_8N1, activeRxPin, DUMMY_TX_PIN);
    
    Serial.printf("[Auto-Pin Hunter] Now listening on Pin %d (GPIO %d) for 10s | Wire Signal Level: %d | Total Bytes: %lu\n",
                  activeRxPin, activeRxPin, digitalRead(activeRxPin), totalRxBytes);
  }

  // 3. Periodic telemetry refresh every 2.5 seconds to keep dashboards synchronized
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat >= 2500) {
    lastHeartbeat = millis();
    if (!hasReceivedArduinoData) {
      Serial.printf("[ESP32 Heartbeat] Searching Arduino on Pin %d | Signal: %d | Bytes: %lu | (Ensure GND wire is connected!)\n", 
                    activeRxPin, digitalRead(activeRxPin), totalRxBytes);
    } else {
      Serial.printf("[ESP32 Heartbeat] Live Arduino Sync LOCKED on Pin %d -> Stop: %s, ETA: %s, Count: %s\n",
                    activeRxPin, parsedCurrentStop.c_str(), parsedCurrentETA.c_str(), parsedPassengerCount.c_str());
    }
    forwardTelemetryToServer();
  }
}
