#include "rfid_reader.h"

RFIDReader::RFIDReader() : _mfrc522(PIN_RFID_SS, PIN_RFID_RST), _lastScannedTag("") {}

void RFIDReader::begin() {
    SPI.begin(PIN_RFID_SCK, PIN_RFID_MISO, PIN_RFID_MOSI, PIN_RFID_SS);
    _mfrc522.PCD_Init();
    Serial.println("[RFIDReader] RC522 Reader Initialized.");
}

bool RFIDReader::isCardAvailable() {
    return _mfrc522.PICC_IsNewCardPresent() && _mfrc522.PICC_ReadCardSerial();
}

String RFIDReader::readTagUID() {
    String uidStr = "";
    for (byte i = 0; i < _mfrc522.uid.size; i++) {
        uidStr += String(_mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
        uidStr += String(_mfrc522.uid.uidByte[i], HEX);
    }
    uidStr.toUpperCase();
    _lastScannedTag = uidStr;
    _mfrc522.PICC_HaltA();
    return uidStr;
}

String RFIDReader::getLastScannedTag() const {
    return _lastScannedTag;
}

void RFIDReader::clearLastTag() {
    _lastScannedTag = "";
}
