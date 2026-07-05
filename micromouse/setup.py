from machine import Pin, ADC, PWM, UART
from diagnosticEncoders import Encoders
import time
import os

def setup():
    """User programmed LED, wheel & button setup"""
    leftMezzLED = Pin(12,Pin.OUT) # The LED marked D1 on the left side of the board
    rightMezzLED = Pin(13,Pin.OUT) # The LED marked D2 on the right side of the board
    leftFwd = PWM(Pin(3))
    leftFwd.freq(2000)
    leftFwd.duty_u16(65535)
    leftRev = PWM(Pin(2))
    leftRev.freq(2000)
    leftRev.duty_u16(65535)
    rightFwd = PWM(Pin(4))
    rightFwd.freq(2000)
    rightFwd.duty_u16(65535)
    rightRev = PWM(Pin(5))
    rightRev.freq(2000)
    rightRev.duty_u16(65535)
    leftButton = Pin(15, Pin.IN, Pin.PULL_UP) # The tactile button switch marked SW1
    rightButton = Pin(14, Pin.IN, Pin.PULL_UP) # The tactile button switch marked SW2

    """Wall sensor setup"""
    leftSensor = ADC(28) # input from the left wall sensor
    rightSensor = ADC(26) # input from the right wall sensor
    frontSensor = ADC(27) # input from the front wall sensor
    #Triggers for LEDs
    sidesEmitter = Pin(22,Pin.OUT) # switches on the 2 side facing wall illumination LEDs
    frontEmitter = Pin(21,Pin.OUT) # switches on the forward facing wall illumination LEDs
    # These are the indicator LEDs on the wall sensor board
    leftSensorLED = Pin(20,Pin.OUT) # indicator LED for when left wall seen
    centreSensorLED = Pin(19,Pin.OUT) # indicator LED for when front wall seen
    rightSensorLED = Pin(18,Pin.OUT) # indicator LED for when right wall seen
    
    return leftMezzLED, rightMezzLED, leftFwd, leftRev, rightFwd, rightRev, leftButton, rightButton, leftSensor, rightSensor, frontSensor, sidesEmitter, frontEmitter, leftSensorLED, centreSensorLED, rightSensorLED