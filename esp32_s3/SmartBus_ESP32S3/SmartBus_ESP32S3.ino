#define BLYNK_TEMPLATE_ID "TMPL3Uzav4bAo"
#define BLYNK_TEMPLATE_NAME "Smart Bus System"
#define BLYNK_AUTH_TOKEN "xL6gh9pcY8-rh9m3708D9AC9QZPfJJ0H"

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>

char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "vivo-1906";       // Wi-Fi Name (Hotspot)
char pass[] = "samarth.akkasali";   // Wi-Fi Password

// Live Python backend server endpoint route parsing JSON fields
// Current Local IP of this laptop running python run.py
const char* serverUrl = "http://192.168.17.168:5000/api/esp32/telemetry";

// Camera-Safe SPI pin footprints for the ESP32-S3
#define RFID_SS   10  
#define RFID_MOSI 11  
#define RFID_MISO 12  
#define RFID_SCK  13  
#define RFID_RST  14  

MFRC522 rfid(RFID_SS, RFID_RST);

const double START_LAT = 12.9716; const double START_LON = 77.5946;
const double DEST_LAT = 13.0105;  const double DEST_LON = 77.5540;

double currentLat = START_LAT; double currentLon = START_LON;
double liveDistanceKm = 6.2;   int liveEtaMinutes = 15;
int localCountFromUno = 0;

bool isBusMoving = false;
unsigned long lastMapUpdate = 0;
int stepCounter = 0;
const int TOTAL_STEPS = 20; 
String currentZone = "Route Start";

void setup() {
  Serial.begin(115200);
  Serial.println("\n[ESP32-S3] Initializing Smart Bus Controller for SB-101...");
  
  // Set up Serial1 to stream data out on GPIO 17 (TX) and listen on GPIO 16 (RX) at 9600 speed
  Serial1.begin(9600, SERIAL_8N1, 16, 17); 
  
  Blynk.begin(auth, ssid, pass);
  
  SPI.begin(RFID_SCK, RFID_MISO, RFID_MOSI, RFID_SS);
  rfid.PCD_Init();
  
  // Free-tier format: Pushing location out as text to bypass paywall
  Blynk.virtualWrite(V1, String(START_LAT, 6) + "," + String(START_LON, 6));
  Blynk.virtualWrite(V4, "STATUS: STATION IDLE");
  
  Serial.println("[ESP32-S3] Setup complete. Connecting telemetry to backend...");
  sendTelemetryToWebsite();
}

void loop() {
  Blynk.run();
  
  // 1. Intercept passenger count metrics streamed up from the Arduino Uno/Mega
  if (Serial1.available() > 0) {
    String incomingPayload = Serial1.readStringUntil('\n');
    incomingPayload.trim();
    if (incomingPayload.startsWith("COUNT:")) {
      localCountFromUno = incomingPayload.substring(6).toInt();
      Serial.print("[ESP32-S3] Received Passenger Count from Arduino: ");
      Serial.println(localCountFromUno);
      Blynk.virtualWrite(V5, localCountFromUno); // Updates Blynk Passenger Gauge
    }
  }

  // 2. Scan for physical RFID card tap
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    isBusMoving = true;
    stepCounter = 0;
    currentZone = "Hospital Stop"; // Initial stop designation upon card swipe trigger
    Serial.println("[ESP32-S3] RFID Card Tapped! Starting journey to Hospital Stop...");
    
    // Command the Uno/Mega down Pin 17 to flash its Blue Alert LED and display the new stop name
    Serial1.println("TAP," + currentZone);
    
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    delay(1000);
  }

  // 3. Simulation Calculation Engine (Updates every 2 seconds)
  if (isBusMoving && (millis() - lastMapUpdate > 2000)) {
    lastMapUpdate = millis();
    stepCounter++;

    if (stepCounter <= TOTAL_STEPS) {
      double fraction = (double)stepCounter / TOTAL_STEPS;
      currentLat = START_LAT + (DEST_LAT - START_LAT) * fraction;
      currentLon = START_LON + (DEST_LON - START_LON) * fraction;
      liveDistanceKm = 6.2 * (1.0 - fraction);
      liveEtaMinutes = (int)((liveDistanceKm / 25.0) * 60.0);

      // Track upcoming route progress bounds to update stop description strings
      if (fraction < 0.25) currentZone = "Hospital Stop";
      else if (fraction < 0.55) currentZone = "Market Area";
      else if (fraction < 0.85) currentZone = "School Zone";
      else currentZone = "Bus Terminal";

      // Send coordinates as pure text to your free String Datastream
      Blynk.virtualWrite(V1, String(currentLat, 6) + "," + String(currentLon, 6));
      Blynk.virtualWrite(V2, liveDistanceKm); 
      Blynk.virtualWrite(V3, liveEtaMinutes);
      Blynk.virtualWrite(V4, "STATUS: EN ROUTE - " + currentZone);

      // CRITICAL UPDATE: Ship the live changing stop name frame downstream to the Arduino Pin 19 / Pin 10
      Serial1.println("TAP," + currentZone);

      sendTelemetryToWebsite();
    } else {
      isBusMoving = false;
      currentZone = "Bus Terminal";
      Blynk.virtualWrite(V1, String(DEST_LAT, 6) + "," + String(DEST_LON, 6));
      Blynk.virtualWrite(V4, "STATUS: ARRIVED");
      
      // Update local physical screen to the terminal finish line status
      Serial1.println("TAP," + currentZone);
      
      sendTelemetryToWebsite();
    }
  }
}

void sendTelemetryToWebsite() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    // Standard JSON payload matching Python backend schema for Bus SB-101
    String jsonPayload = "{\"bus_number\":\"SB-101\",\"bus_id\":\"SB-101\",\"passengers\":" + String(localCountFromUno) + 
                         ",\"passenger_count\":" + String(localCountFromUno) + 
                         ",\"latitude\":" + String(currentLat, 6) + 
                         ",\"longitude\":" + String(currentLon, 6) + 
                         ",\"current_stop\":\"" + currentZone + "\",\"distance\":" + String(liveDistanceKm, 1) + 
                         ",\"eta\":" + String(liveEtaMinutes) + "}";

    Serial.print("[ESP32-S3] Sending Telemetry: ");
    Serial.println(jsonPayload);

    int httpResponseCode = http.POST(jsonPayload);
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.print("[ESP32-S3] Telemetry HTTP Code: ");
      Serial.println(httpResponseCode);
      Serial.print("[ESP32-S3] Backend Response: ");
      Serial.println(response);

      // If backend AI agent triggered an alert (e.g. drowsiness / overcrowding alert)
      if (response.indexOf("\"buzzer\":true") >= 0 || response.indexOf("\"alert_code\"") >= 0) {
        Serial1.println("ALERT:DANGER");
      }
    } else {
      Serial.print("[ESP32-S3] Telemetry POST failed, error code: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  } else {
    Serial.println("[ESP32-S3] Wi-Fi not connected! Cannot send telemetry.");
  }
}
