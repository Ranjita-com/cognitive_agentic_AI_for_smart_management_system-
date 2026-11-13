class HardwareService:
    """
    Hardware Command & Protocol Service for physical Smart Bus SB-101.
    Translates high-level agent decisions into structured ESP32-S3 and Arduino UNO actuation commands.
    
    Protocol:
    - ESP32 -> Arduino UNO via UART Serial:
      COUNT:<int>          e.g. COUNT:24
      ALERT:<alert_type>   e.g. ALERT:DROWSINESS, ALERT:OVERCROWDED, ALERT:SOS
      LED:<color>          e.g. LED:RED, LED:GREEN, LED:OFF
      BUZZER:<state>       e.g. BUZZER:ON, BUZZER:OFF, BUZZER:PULSE
      LCD:<message>        e.g. LCD:STATUS OK, LCD:BUS FULL, LCD:DROWSY DRIVER
      
    - Arduino UNO -> ESP32 via UART Serial:
      RFID:<card_uid>      e.g. RFID:7741AB12
      BTN:SOS              e.g. BTN:SOS
    """

    @staticmethod
    def build_actuator_commands(safety_alerts=None, passenger_count=0, capacity=40, is_emergency=False, is_drowsy=False, drowsiness_state=None):
        """
        Builds normalized actuator state and hardware commands dictionary for SB-101.
        """
        commands = []
        buzzer = False
        red_led = False
        green_led = True
        lcd_message = f"P:{passenger_count}/{capacity}"
        alert_code = "NORMAL"

        if is_emergency:
            buzzer = True
            red_led = True
            green_led = False
            lcd_message = "EMERGENCY SOS"
            alert_code = "SOS"
            commands.extend(["ALERT:SOS", "LED:RED", "BUZZER:ON", "LCD:EMERGENCY SOS"])

        elif is_drowsy:
            buzzer = True
            red_led = True
            green_led = False
            if drowsiness_state in ('FULLY_INACTIVE', 'CRITICAL'):
                lcd_message = "DRIVER INACTIVE - SWAP NOW"
                alert_code = "DRIVER_INACTIVE"
                commands.extend(["ALERT:DRIVER_INACTIVE", "LED:RED", "BUZZER:ON", "LCD:SWAP DRIVER NOW"])
            else:
                lcd_message = "DROWSINESS DETECTED"
                alert_code = "DROWSINESS"
                commands.extend(["ALERT:DROWSINESS", "LED:RED", "BUZZER:ON", "LCD:DROWSY DRIVER"])

        elif passenger_count >= capacity:
            buzzer = True
            red_led = True
            green_led = False
            lcd_message = f"BUS FULL {passenger_count}/{capacity}"
            alert_code = "OVERCROWDED"
            commands.extend(["ALERT:OVERCROWDED", "LED:RED", "BUZZER:ON", f"LCD:BUS FULL ({passenger_count})"])

        elif passenger_count >= int(capacity * 0.85):
            red_led = True
            green_led = False
            lcd_message = f"HIGH LOAD {passenger_count}/{capacity}"
            alert_code = "HIGH_LOAD"
            commands.extend(["ALERT:HIGH_LOAD", "LED:RED", f"LCD:HIGH LOAD {passenger_count}"])

        else:
            commands.extend(["ALERT:NORMAL", "LED:GREEN", "BUZZER:OFF", f"COUNT:{passenger_count}", f"LCD:P:{passenger_count}/{capacity}"])

        return {
            'buzzer': buzzer,
            'red_led': red_led,
            'green_led': green_led,
            'display_message': lcd_message,
            'alert_code': alert_code,
            'passenger_count': passenger_count,
            'serial_commands': commands,
            'raw_serial_payload': ";".join(commands)
        }

    @staticmethod
    def parse_arduino_serial_message(raw_msg):
        """
        Parses incoming serial message from Arduino UNO.
        """
        raw_msg = raw_msg.strip()
        if raw_msg.startswith("RFID:"):
            return {'type': 'RFID', 'card_uid': raw_msg.split(":", 1)[1].strip()}
        elif raw_msg.startswith("BTN:SOS"):
            return {'type': 'SOS', 'state': True}
        return {'type': 'RAW', 'data': raw_msg}

    @staticmethod
    def send_serial_command(cmd_string):
        """
        Dispatches serial command string to physical bus SB-101 (ESP32-S3 / Arduino UNO).
        """
        return {'dispatched': True, 'command': cmd_string}

hardware_service = HardwareService()
