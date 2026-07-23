"""Hardware and Pin Setup for UKMARS Gemini / RP2040.

Identical code runs on Pico and PC:
- On Pico, MicroPython loads its native C machine module.
- On PC, Python imports the mock machine.py module.
"""

from machine import Pin, ADC, PWM

# Digital output pins
LED_PIN = Pin(18, Pin.OUT)
RMOTOR_DIR = Pin(8, Pin.OUT)
LMOTOR_DIR = Pin(7, Pin.OUT)
PIEZO_PIN = Pin(22, Pin.OUT)
SENSOR1_PIN = Pin(19, Pin.OUT)
SENSOR2_PIN = Pin(6, Pin.OUT)
TRIGGER_PIN = Pin(16, Pin.OUT)

# Motor PWM pins (active low: 65535 = OFF, lower = faster)
LMOTOR_PIN = Pin(9, Pin.OUT)
RMOTOR_PIN = Pin(17, Pin.OUT)
LMOTOR_PWM = PWM(LMOTOR_PIN)
RMOTOR_PWM = PWM(RMOTOR_PIN)

LMOTOR_PWM.freq(2000)
RMOTOR_PWM.freq(2000)
LMOTOR_PWM.duty_u16(65535)  # Default OFF
RMOTOR_PWM.duty_u16(65535)  # Default OFF

# Reflective sensor ADC inputs
Lsidesense = ADC(Pin(29))   # Left side sensor
Lfrontsense = ADC(Pin(28))  # Front sensor
Rfrontsense = ADC(Pin(27))  # Front sensor
Rsidesense = ADC(Pin(26))   # Right side sensor

# Buttons / Switches
btn1 = Pin(20, Pin.IN, Pin.PULL_UP)
Switch = Pin(14, Pin.IN, Pin.PULL_UP)
