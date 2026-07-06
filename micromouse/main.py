from machine import Pin, ADC, PWM, UART
import time
import os

from setup import setup
from diagnosticEncoders import Encoders

import config, explorer, env_explorer, maze, search_algorithms



# Initialize the encoders
encoders = Encoders()

leftMezzLED, rightMezzLED, leftFwd, leftRev, rightFwd, rightRev, leftButton, rightButton, leftSensor, rightSensor, frontSensor, sidesEmitter, frontEmitter, leftSensorLED, centreSensorLED, rightSensorLED = setup()
maxspeed = 65535 
botspeed = maxspeed - 15000
leftFwd.duty_u16(maxspeed)
rightFwd.duty_u16(maxspeed)
toggle_red_LED = 1

global leftSensorValue, rightSensorValue, frontSensorValue
global leftSensorLit, rightSensorLit, frontSensorLit
global leftSensorUnlit, rightSensorUnlit, frontSensorUnlit

def stop_motors():
    leftFwd.duty_u16(maxspeed)
    leftRev.duty_u16(maxspeed)
    rightFwd.duty_u16(maxspeed)
    rightRev.duty_u16(maxspeed)

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


"""march to wall"""

def march_to_wall():
    # Record the start time locally
    start_time = time.ticks_ms()
    last_sensor_check = start_time
    near_wall = False
    
    leftMezzLED.on()
    print("march start")
    
    # Motor activation
    leftFwd.duty_u16(botspeed)
    leftRev.duty_u16(maxspeed)
    rightFwd.duty_u16(botspeed)
    rightRev.duty_u16(maxspeed)

    while not near_wall:
        now = time.ticks_ms() # Update time every iteration
        
        if time.ticks_diff(now, last_sensor_check) >= 500: # Check sensors every 500ms
            readSensors()
            print(leftSensorValue,frontSensorValue, rightSensorValue)
            last_sensor_check = now # Reset interval
            
            if leftSensorValue > 7000 or rightSensorValue > 7000 or frontSensorValue > 7000:
                print("wall detected")
                near_wall = True
            
        if rightButton.value() == 0: # Emergency Stop Button (checked constantly)
            print("user interrupted")
            near_wall = True
            
        # Safety Timeout
        if time.ticks_diff(now, start_time) > 60000:
            print("time hit")
            break

    stop_motors()
    leftMezzLED.off()

while True:
    current_time = time.ticks_ms()
        
    if current_time % 1000 == 0:
        if toggle_red_LED == 0:
            rightMezzLED.off()
        if toggle_red_LED == 1:
            rightMezzLED.on()
        toggle_red_LED = 1 - toggle_red_LED
        
        # Print encoder values every second
        print("Encoders (Left, Right):", encoders.get_counts())
        
        time.sleep(0.001)

    # Left Button starts march
    if leftButton.value() == 0:
        rightMezzLED.off()
        leftMezzLED.on()
        march_to_wall()
        leftMezzLED.off()
    
    if current_time % 1000 == 0:
        if toggle_red_LED == 0:
            rightMezzLED.off()
        if toggle_red_LED == 1:
            rightMezzLED.on()
        toggle_red_LED = 1 - toggle_red_LED
        time.sleep(0.001)


    if current_time % 5000 == 0:
        print(current_time)
        time.sleep(0.001)
    
    if current_time > 300000:
        print("time hit")
        break

leftMezzLED.off()
rightMezzLED.off()
stop_motors()

maze_test = maze.MazeStructure()
# search_algo (maze_test, 0,0)
#-> list of coordinates

#