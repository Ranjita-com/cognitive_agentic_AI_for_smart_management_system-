#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SoftwareSerial.h>
#include <TinyGPS++.h>

// I2C LCD (0x27 address, 16 columns x 2 rows)
// On Arduino Mega: Pin 20 (SDA), Pin 21 (SCL)
// On Arduino Uno:  Pin A4 (SDA), Pin A5 (SCL)
LiquidCrystal_I2C lcd(0x27, 16, 2); 

// IR Sensor Pins (Connected to 3.3V VCC)
#define IR1_PIN A0   // Entry Sensor (OUT to A0)
#define IR2_PIN A1   // Exit Sensor  (OUT to A1)
#define SIMULATION_BUTTON_PIN 5 // Push button between Pin 5 and GND

// Status LEDs
const int GREEN_LED  = 3; 
const int YELLOW_LED = 4; 
const int BLUE_LED   = 7; 
const int RED_LED    = 8; 

int passengerCount = 0;
int overcrowdedStatus = 0; // 0 = Normal/High, 1 = Overcrowded (Triggers Web SOS)

// GPS Object
TinyGPSPlus gps;

// Live Coordinates (Default fallback: Bangalore route coordinates)
double currentLat = 12.971600;
double currentLng = 77.594600;

// Communication to ESP32:
// Arduino Uno: Pin 11 (Uno TX) -> ESP32 RX (GPIO 1), Pin 10 (Uno RX) -> ESP32 TX (GPIO 2)
// Arduino Mega: Pin 18 (TX1) -> ESP32 RX (GPIO 1), Pin 19 (RX1) -> ESP32 TX (GPIO 2)
SoftwareSerial swSerial(10, 11); // RX, TX for Uno

// GPS Serial for Uno: Pin 2 (RX from GPS TX), Pin 6 (TX to GPS RX)
SoftwareSerial gpsSerial(2, 6);

// Master Bus Stop Database
const char* masterStops[] = {"Hospital Stop", "School Zone", "Market Area", "Bus Terminal"};
const int baseETAs[] = {25, 15, 8, 0}; 
const double stopLats[] = {12.971600, 12.981900, 12.992200, 13.001000};
const double stopLngs[] = {77.594600, 77.605200, 77.615900, 77.625000}; 

// Route Phase Management
int shuffledOrder[4] = {0, 1, 2, 3};
int totalButtonPresses = 0;
int shuffleIndex = 0;

int currentStopIndex = 0;
int currentETA = 25;

unsigned long lastETADecouple = 0;
const unsigned long etaCountdownInterval = 5000; // Drops 1 min every 5 sec for demo

bool ir1Triggered = false;
bool ir2Triggered = false;
unsigned long sequenceStartTime = 0;
const unsigned long sequenceTimeout = 1500; 

// Hardware Serial detection for Arduino Mega vs Uno
#if defined(__AVR_ATmega2560__) || defined(__AVR_ATmega1280__) || defined(HAVE_HWSERIAL1)
  #define IS_MEGA 1
#else
  #define IS_MEGA 0
#endif

void sendBusTelemetry() {
  String packet = "BUS_DATA:Count=" + String(passengerCount) +
                  "&Stop=" + String(masterStops[currentStopIndex]) +
                  "&ETA=" + String(currentETA) +
                  "&SOS=" + String(overcrowdedStatus) +
                  "&Lat=" + String(currentLat, 6) +
                  "&Lng=" + String(currentLng, 6);
  
  // 1. Transmit over standard Serial (USB Monitor to PC & Pin 1 TX0)
  Serial.println(packet);
  
#if IS_MEGA
  // 2. Transmit over Hardware Serial1 (Pin 18 TX1 on Arduino Mega)
  Serial1.println(packet);
  // 3. Transmit over Hardware Serial3 (Pin 14 TX3 on Arduino Mega)
  Serial3.println(packet);
#else
  // 4. Transmit over SoftwareSerial (Pin 11 TX on Uno)
  swSerial.println(packet);
#endif
}

void setup() {
  // Serial0: PC Debugging and Pin 1 (TX0)
  Serial.begin(115200);

#if IS_MEGA
  Serial1.begin(115200); // Dedicated Mega Serial1 to ESP32 (Pin 18 TX1)
  Serial3.begin(115200); // Dedicated Mega Serial3 to ESP32 (Pin 14 TX3)
  Serial2.begin(9600);   // Dedicated Mega Serial2 to GPS (Pin 17 RX2)
  Serial.println(F("[SYSTEM] Board Detected: ARDUINO MEGA (Active on Pin 1 TX0, Pin 18 TX1 & Pin 14 TX3)"));
#else
  gpsSerial.begin(9600);   // Uno to GPS (Pins 2 RX / 6 TX)
  swSerial.begin(115200);  // Uno to ESP32
  Serial.println(F("[SYSTEM] Board Detected: ARDUINO UNO (Active on Pin 1 TX0 & Pin 11 TX)"));
#endif

  pinMode(GREEN_LED, OUTPUT); 
  pinMode(YELLOW_LED, OUTPUT); 
  pinMode(RED_LED, OUTPUT); 
  pinMode(BLUE_LED, OUTPUT);
  digitalWrite(BLUE_LED, LOW);
  
  // 3.3V IR SENSORS: Use INPUT mode (NOT INPUT_PULLUP) to avoid sending 5V into 3.3V sensor
  pinMode(IR1_PIN, INPUT);
  pinMode(IR2_PIN, INPUT);
  pinMode(SIMULATION_BUTTON_PIN, INPUT_PULLUP); 
  
  randomSeed(analogRead(A3));

  Wire.begin(); 
  lcd.init(); 
  lcd.backlight();
  
  lcd.setCursor(0, 0); lcd.print(" SMART BUS MEGA ");
  lcd.setCursor(0, 1); lcd.print(" ROUTE: SB-101 ");
  delay(1200);
  
  updateLocalLCD();
  sendBusTelemetry();

  Serial.println("\n========================================================");
  Serial.println("  Smart Bus Controller Active (SB-101) ");
  Serial.println("  - Mega Pin 18 (TX1) -> ESP32-S3 Pin 1 (RX)");
  Serial.println("  - Mega Pin 17 (RX2) <- GPS Module TX (9600 Baud)");
  Serial.println("  - IR Sensors on 3.3V: Pin A0 (IR1 In) & Pin A1 (IR2 Out)");
  Serial.println("  - Push Button: Pin 5 to GND (Cycles Stops)");
  Serial.println("  - Arduino GND -> ESP32 GND (COMMON GROUND REQUIRED)");
  Serial.println("========================================================\n");
}

void loop() {
  // 1. Ingest GPS NMEA sentences
#if IS_MEGA
  while (Serial2.available() > 0) {
    gps.encode(Serial2.read());
  }
#else
  gpsSerial.listen();
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
#endif

  // If valid GPS fix is acquired, update coordinates
  if (gps.location.isValid()) {
    currentLat = gps.location.lat();
    currentLng = gps.location.lng();
  }

  // 2. Process IR Passenger entry/exit
  checkLocalPassengerMovement();

  // 3. Process Bus Stop Push Button
  checkStopChangeButton();

  // 4. Update ETA countdown
  updateETACountdown();

  // 5. Periodic heartbeat broadcast every 2 seconds
  static unsigned long lastStreamTime = 0;
  if (millis() - lastStreamTime >= 2000) {
    lastStreamTime = millis();
    sendBusTelemetry();
  }

  manageDensityIndicators();
  delay(10);
}

void checkLocalPassengerMovement() {
  int ir1 = digitalRead(IR1_PIN);
  int ir2 = digitalRead(IR2_PIN);
  
  // LM393 IR Sensors output LOW when obstacle/passenger is detected
  bool s1Active = (ir1 == LOW); 
  bool s2Active = (ir2 == LOW);

  // Passenger Entry: IR1 triggered first, then IR2
  if (s1Active && !ir1Triggered && !ir2Triggered) {
    ir1Triggered = true;
    sequenceStartTime = millis();
  }
  if (ir1Triggered && s2Active) {
    passengerCount++;
    ir1Triggered = false; 
    ir2Triggered = false;
    updateLocalLCD();
    sendBusTelemetry();
    delay(400); 
  }

  // Passenger Exit: IR2 triggered first, then IR1
  if (s2Active && !ir2Triggered && !ir1Triggered) {
    ir2Triggered = true;
    sequenceStartTime = millis();
  }
  if (ir2Triggered && s1Active) {
    if (passengerCount > 0) passengerCount--;
    ir1Triggered = false; 
    ir2Triggered = false;
    updateLocalLCD();
    sendBusTelemetry();
    delay(400); 
  }

  // Sequence timeout (reset if person paused or stepped back)
  if ((ir1Triggered || ir2Triggered) && (millis() - sequenceStartTime > sequenceTimeout)) {
    ir1Triggered = false; 
    ir2Triggered = false;
  }
}

void shuffleRoutePool() {
  for (int i = 3; i > 0; i--) {
    int j = random(0, i + 1);
    int temp = shuffledOrder[i];
    shuffledOrder[i] = shuffledOrder[j];
    shuffledOrder[j] = temp;
  }
  shuffleIndex = 0;
}

void checkStopChangeButton() {
  static unsigned long lastBtnPress = 0;
  if (digitalRead(SIMULATION_BUTTON_PIN) == LOW && (millis() - lastBtnPress > 350)) {
    lastBtnPress = millis();
    triggerButtonFeedback();
    totalButtonPresses++;

    if (totalButtonPresses <= 4) {
      currentStopIndex = totalButtonPresses - 1;
      if (totalButtonPresses == 4) {
        shuffleRoutePool();
      }
    } else {
      currentStopIndex = shuffledOrder[shuffleIndex];
      shuffleIndex++;
      if (shuffleIndex >= 4) {
        shuffleRoutePool();
      }
    }

    currentETA = baseETAs[currentStopIndex];
    if (!gps.location.isValid()) {
      currentLat = stopLats[currentStopIndex];
      currentLng = stopLngs[currentStopIndex];
    }
    updateLocalLCD();
    sendBusTelemetry(); // Immediately notify ESP32 and website of new stop!
    lastETADecouple = millis();
  }
}

void updateETACountdown() {
  if (currentETA > 0) {
    if (millis() - lastETADecouple >= etaCountdownInterval) {
      currentETA--;
      lastETADecouple = millis();

      // If no valid outdoor GPS satellite fix, calculate intermediate coordinates between stops
      if (!gps.location.isValid()) {
        int nextIdx = (currentStopIndex < 3) ? (currentStopIndex + 1) : 3;
        int legStartETA = baseETAs[currentStopIndex];
        int legEndETA   = baseETAs[nextIdx];

        if (legStartETA > legEndETA) {
          float legProgress = (float)(legStartETA - currentETA) / (float)(legStartETA - legEndETA);
          if (legProgress > 1.0) legProgress = 1.0;
          if (legProgress < 0.0) legProgress = 0.0;

          currentLat = stopLats[currentStopIndex] + legProgress * (stopLats[nextIdx] - stopLats[currentStopIndex]);
          currentLng = stopLngs[currentStopIndex] + legProgress * (stopLngs[nextIdx] - stopLngs[currentStopIndex]);

          // Automatically arrive at next stop when countdown reaches next stop's ETA
          if (currentETA <= legEndETA && currentStopIndex < 3) {
            currentStopIndex = nextIdx;
            currentETA = baseETAs[currentStopIndex];
            currentLat = stopLats[currentStopIndex];
            currentLng = stopLngs[currentStopIndex];
            triggerButtonFeedback(); // Signal arrival with brief LED flash
          }
        }
      }

      updateLocalLCD();
      sendBusTelemetry();
    }
  }
}

void triggerButtonFeedback() {
  digitalWrite(BLUE_LED, HIGH); delay(60); digitalWrite(BLUE_LED, LOW); delay(60);
  digitalWrite(BLUE_LED, HIGH); delay(60); digitalWrite(BLUE_LED, LOW);
}

void updateLocalLCD() {
  lcd.clear();
  lcd.setCursor(0, 0); 
  lcd.print("P:"); 
  lcd.print(passengerCount);
  lcd.print(" ");
  lcd.print(masterStops[currentStopIndex]);
  
  lcd.setCursor(0, 1); 
  if (currentETA > 0) {
    lcd.print("ETA: "); 
    lcd.print(currentETA);
    lcd.print(" Mins");
  } else {
    lcd.print("Terminal Reached");
  }
}

void manageDensityIndicators() {
  digitalWrite(GREEN_LED, LOW); 
  digitalWrite(YELLOW_LED, LOW); 
  digitalWrite(RED_LED, LOW);
  
  if (passengerCount < 4) {
    digitalWrite(GREEN_LED, HIGH);
    overcrowdedStatus = 0; 
  } else if (passengerCount < 8) {
    digitalWrite(YELLOW_LED, HIGH);
    overcrowdedStatus = 0; 
  } else {
    digitalWrite(RED_LED, HIGH);
    overcrowdedStatus = 1; 
  }
}
