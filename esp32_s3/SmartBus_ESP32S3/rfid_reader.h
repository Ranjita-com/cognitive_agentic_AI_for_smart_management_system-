#ifndef RFID_READER_H
#define RFID_READER_H

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include "pins.h"

class RFIDReader {
public:
    RFIDReader();
    void begin();
    bool isCardAvailable();
    String readTagUID();
    String getLastScannedTag() const;
    void clearLastTag();

private:
    MFRC522 _mfrc522;
    String _lastScannedTag;
};

#endif // RFID_READER_H
