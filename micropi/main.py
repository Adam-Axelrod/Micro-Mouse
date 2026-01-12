from machine import Pin, ADC, PWM, UART
import time
import os

"""User programmed LED, wheel & button setup"""
leftMezzLED = Pin(12,Pin.OUT) # The LED marked D1 on the left side of the board
rightMezzLED = Pin(13,Pin.OUT) # The LED marked D2 on the right side of the board
leftFwd = PWM(Pin(2))
leftFwd.freq(2000)
leftRev = PWM(Pin(3))
leftRev.freq(2000)
rightFwd = PWM(Pin(4))
rightFwd.freq(2000)
rightRev = PWM(Pin(5))
rightRev.freq(2000)
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

"""Wheel and LED blinking test"""
# Run motors forward and backwards and light the LEDs then stop motors
maxspeed = 65535 
botspeed = maxspeed - 15000 # desired speed of 15000
leftMezzLED.on() # Switch on the left mezzanine LED
leftFwd.duty_u16(maxspeed) # Set left forward speed to maxspeed
leftRev.duty_u16(botspeed) # and reverse speed to maxspeed - desired speed of 15000
rightFwd.duty_u16(maxspeed) # Set right forward speed to maxspeed
rightRev.duty_u16(botspeed) # and reverse speed to maxspeed - desired speed of 15000
time.sleep(5) # Wait for 5 seconds
leftMezzLED.off() # Switch off the left mezzanine LED
rightMezzLED.on() # Switch on the right mezzanine LED
leftRev.duty_u16(maxspeed) # Set left reverse speed to maxspeed
leftFwd.duty_u16(botspeed) # and forward speed to desired reverse speed of 15000
rightRev.duty_u16(maxspeed) # Set left reverse speed to maxspeed
rightFwd.duty_u16(botspeed) # and forward speed to desired reverse speed of 15000
time.sleep(5) # Wait for 5 seconds
leftMezzLED.off() # Switch off the left mezzanine LED
rightMezzLED.off() # Switch off the right mezzanine LED
leftFwd.duty_u16(maxspeed) # Set left forward speed to zero
leftRev.duty_u16(maxspeed) # and reverse speed to zero
rightFwd.duty_u16(maxspeed) # Set right forward speed to zero
rightRev.duty_u16(maxspeed) # and reverse speed to zero


"""Sensor test
def readSensors():
    #Values are derived by subtracting the unlit value of a sensor from the lit value  
    global leftSensorValue, rightSensorValue, frontSensorValue
    global leftSensorLit, rightSensorLit, frontSensorLit
    global leftSensorUnlit, rightSensorUnlit, frontSensorUnlit

    leftSensorUnlit = leftSensor.read_u16()
    rightSensorUnlit = rightSensor.read_u16()
    sidesEmitter.value(1)
    time.sleep_us(75)
    leftSensorLit = leftSensor.read_u16()
    rightSensorLit = rightSensor.read_u16()
    sidesEmitter.value(0)
    
    frontSensorUnlit = frontSensor.read_u16()    
    frontEmitter.value(1)
    time.sleep_us(75)
    frontSensorLit = frontSensor.read_u16()
    frontEmitter.value(0)
    time.sleep_us(75)

    leftSensorValue = (leftSensorLit - leftSensorUnlit)
    rightSensorValue = (rightSensorLit- rightSensorUnlit) 
    frontSensorValue = (frontSensorLit- frontSensorUnlit)
    
def printSensors():
    global leftSensorValue, rightSensorValue, frontSensorValue
    global leftSensorLit, rightSensorLit, frontSensorLit
    global leftSensorUnlit, rightSensorUnlit, frontSensorUnlit
    while True:
        readSensors()
        print("left front right")
        print(leftSensorValue,frontSensorValue, rightSensorValue)
        time.sleep(0.5)
# run the program
printSensors() # call the printSensors programe

"""
