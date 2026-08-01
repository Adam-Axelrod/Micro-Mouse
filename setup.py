"""Hardware and Pin Setup for UKMARS Gemini / RP2040.

Identical code runs on Pico and PC:
- On Pico, MicroPython loads its native C machine module.
- On PC, Python imports the mock sim_machine.py module.
"""
# The platform probe and the sim import happen HERE and only here: setup.py is
# the hardware boundary. On PC, `sim` exposes the simulation engine (world
# loading, physics stepping, true pose); on the Pico it is None and the pin
# objects below are the real thing.
try:
    from machine import Pin, ADC, PWM
    IS_HARDWARE = True   # real MicroPython machine module (Pico)
    sim = None           # no simulation engine on hardware
except ImportError:
    import sim_machine as sim
    from sim_machine import Pin, ADC, PWM
    IS_HARDWARE = False  # PC: the sim engine stands in for the hardware

# Motor PWM pins (2 PWM channels per motor; active low: 65535 = OFF, lower = faster)
leftFwd = PWM(Pin(3))
leftRev = PWM(Pin(2))
rightFwd = PWM(Pin(4))
rightRev = PWM(Pin(5))

for pwm_chan in (leftFwd, leftRev, rightFwd, rightRev):
    pwm_chan.freq(2000)
    # Both channels of a motor held at 65535 = BRAKE (bench-confirmed 2026-08-01,
    # BT-3: the wheels stop dead, they do not freewheel). A single channel at
    # 65535 with the other driven low is that channel OFF, i.e. normal drive.
    pwm_chan.duty_u16(65535)

# Tactile Buttons / Mode Switches (SW1 / SW2)
leftButton = Pin(15, Pin.IN, Pin.PULL_UP)   # SW1: Left button (Exploration)
rightButton = Pin(14, Pin.IN, Pin.PULL_UP)  # SW2: Right button (Speed Run)

# Reflective sensor ADC inputs (phototransistors)
leftSensor = ADC(28)   # Left wall sensor
frontSensor = ADC(27)  # Front wall sensor
rightSensor = ADC(26)  # Right wall sensor

# Emitter Triggers
sidesEmitter = Pin(22, Pin.OUT)  # Side IR illumination LEDs
frontEmitter = Pin(21, Pin.OUT)  # Front IR illumination LED

# Indicator & Status LEDs
leftSensorLED = Pin(20, Pin.OUT)    # Left wall detected LED
centreSensorLED = Pin(19, Pin.OUT)  # Front wall detected LED
rightSensorLED = Pin(18, Pin.OUT)   # Right wall detected LED
leftMezzLED = Pin(12, Pin.OUT)      # Left Mezzanine LED D1
rightMezzLED = Pin(13, Pin.OUT)     # Right Mezzanine LED D2
# Onboard LED: the named "LED" pin on the Pico (W boards route it via the wireless
# chip, so the name matters); plain numeric pin for the PC mock.
LED_PIN = Pin("LED", Pin.OUT) if IS_HARDWARE else Pin(25, Pin.OUT)

# Backward-compatibility aliases
btn1 = leftButton
Switch = rightButton
Lsidesense = leftSensor
Lfrontsense = frontSensor
Rfrontsense = frontSensor
Rsidesense = rightSensor
LMOTOR_PWM = leftFwd
RMOTOR_PWM = rightFwd

