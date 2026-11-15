"""Hardware and Pin Setup for UKMARS Gemini / RP2040.

Identical code runs on Pico and PC:
- On Pico, MicroPython loads its native C machine module.
- On PC, Python imports the mock sim_machine.py module.

This file is the platform boundary. It is the one place that knows which of the
two is running, and it hands every other module what it needs as a name:

    pins and handles    leftFwd, sw1, LED_PIN, ... and read_encoders()
    time                wait(seconds), now_ms(), diff_ms(new, old)
    the run's world     scene(map_path, grid, start_pose, render)
    platform facts      TRACE_BY_DEFAULT, REAL_BOARD

On the robot `wait` sleeps and the clock is the board's. On the PC `wait` steps
the simulated physics and the clock is simulated time. `scene()` is a stand-in
that does nothing on the robot, and the simulated world on the PC.
"""
# The platform probe and the sim imports happen HERE and only here. On the Pico
# `sim` is None and the pin objects below are the real thing. On PC `sim` is the
# mock machine module, and the rest of `sim/` is never imported on the board.
try:
    from machine import Pin, ADC, PWM
    import time
    IS_HARDWARE = True   # real MicroPython machine module (Pico)
    sim = None           # no simulation engine on hardware

    wait = time.sleep
    # MicroPython's tick clock wraps, so it has its own difference. CPython has
    # neither name, and the deployment check boots this branch there.
    if hasattr(time, "ticks_ms"):
        now_ms = time.ticks_ms
    else:
        def now_ms():
            return int(time.monotonic() * 1000.0)
    if hasattr(time, "ticks_diff"):
        diff_ms = time.ticks_diff
    else:
        def diff_ms(new_ms, old_ms):
            return new_ms - old_ms

    class _NullScene:
        """The robot has no world to draw or to place the mouse in."""

        def show(self, belief=None, route=None, done=None, animate=False):
            pass

        def pose(self):
            return None

    def scene(map_path=None, grid=None, start_pose=None, render=False):
        """The run's world. On the robot, a scene whose methods do nothing."""
        return _NullScene()

    # A hardware run has no window, so the motor trace is its only record.
    TRACE_BY_DEFAULT = True
    # The pins drive a real board.
    REAL_BOARD = True
except ImportError:
    # PC only. `sim` is the package of never-deployed modules; `sim.sim_machine`
    # is the mock inside it, and it is what the rest of the project calls
    # `setup.sim`.
    from sim import sim_machine as sim
    from sim.sim_machine import Pin, ADC, PWM
    from sim import scene as _sim_scene
    IS_HARDWARE = False  # PC: the sim engine stands in for the hardware

    wait = _sim_scene.wait
    now_ms = _sim_scene.now_ms
    diff_ms = _sim_scene.diff_ms
    scene = _sim_scene.Scene

    # On the PC a trace costs a file for nothing, so `--log` asks for one.
    TRACE_BY_DEFAULT = False
    REAL_BOARD = False

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
leftButton = Pin(15, Pin.IN, Pin.PULL_UP)   # SW1: Left button (Mode selector)
rightButton = Pin(14, Pin.IN, Pin.PULL_UP)  # SW2: Right button (Mode execute)
sw1 = leftButton
sw2 = rightButton

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

# Quadrature encoder inputs (magnetic Hall sensors on the N20 motor shafts).
# The PIO decoder reads an adjacent pin pair, so B is always A + 1. These pins
# are inputs and share nothing with the motor PWM channels above; nothing here
# touches motor polarity.
LEFT_ENCODER_A, LEFT_ENCODER_B = 8, 9
RIGHT_ENCODER_A, RIGHT_ENCODER_B = 6, 7

# Counts per wheel revolution is a designed integer, not a measurement: the
# encoder's edges per motor shaft revolution times the gearbox ratio. It lives
# in config.ENCODER_COUNTS_PER_WHEEL_REV.

_encoders = None
encoder_error = None


def get_encoders():
    """The quadrature decoder, or None if it is unavailable.

    Built on FIRST USE, never at import. On the Pico this claims a PIO state
    machine, and that can fail; setup.py is imported by every module, so a
    failure at import would take the whole robot down instead of one read.

    On the Pico the decoder is the PIO counter in encoders. On the
    PC it reads the simulated tick counters. Both answer
    get_counts(reset=False) with (left_ticks, right_ticks), forward positive.
    """
    global _encoders, encoder_error
    if _encoders is None and encoder_error is None:
        try:
            if IS_HARDWARE:
                from hal.encoders import Encoders
                _encoders = Encoders()
            else:
                _encoders = sim.SimEncoders()
        except Exception as exc:  # missing rp2, PIO already claimed, bad wiring
            encoder_error = str(exc) or exc.__class__.__name__
    return _encoders


def read_encoders(reset=False):
    """(left_ticks, right_ticks), forward positive, or None if unavailable."""
    encoders = get_encoders()
    if encoders is None:
        return None
    return encoders.get_counts(reset=reset)
