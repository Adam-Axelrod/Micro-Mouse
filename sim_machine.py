"""Mock MicroPython machine module for desktop PC simulation.

Provides synthetic Pin, PWM, and ADC classes that mirror MicroPython's C machine module.
Allows setup.py to run unchanged on both PC and Pico.
On PC, writing PWM duties updates the MouseState physics engine, and reading ADC returns
simulated phototransistor light intensity values via raycasting.
"""

import math
import config
from geometry import MazeGeometry
from maze import MazeStructure
from mouse import MouseState


class HardwareSimulation:
    def __init__(self):
        self.mouse = MouseState()
        self.maze = None
        self.segments = []
        self.left_fwd_duty = 65535   # Active-low default (OFF)
        self.left_rev_duty = 65535
        self.right_fwd_duty = 65535
        self.right_rev_duty = 65535
        self.max_wheel_speed_mms = config.MAX_WHEEL_SPEED_MMS  # mm/s at 100% duty
        # Simulated time, advanced only by step_physics. On PC the drive routines
        # step physics instead of sleeping, so wall-clock time is NOT the sim's
        # clock -- anything timestamping sim events must read this instead.
        self.elapsed_seconds = 0.0

        self.adc_pin_map = {
            28: "left",
            27: "front",
            26: "right",
            29: "left",  # fallback
        }

    def load_maze(self, maze_instance):
        self.maze = maze_instance
        self.segments = MazeGeometry(maze_instance).segments

    def set_motor_duty(self, pin_id, duty):
        # Pin map bench-confirmed on the real board 2026-08-01 (BT-2): driving
        # pin 3 alone runs the left wheel forward, and drive_motors(+,+) moved
        # both wheels forward. setup.py was right; this map was inverted.
        # The legacy ids (9, 7, 17, 8) that used to alias these channels are
        # gone: 7 and 8 are encoder inputs, so mapping them to a motor was a
        # latent trap, and pin 3 cannot mean both directions at once.
        if pin_id == 3:
            self.left_fwd_duty = duty
        elif pin_id == 2:
            self.left_rev_duty = duty
        elif pin_id == 4:
            self.right_fwd_duty = duty
        elif pin_id == 5:
            self.right_rev_duty = duty

    def compute_wheel_speeds(self):
        # Gemini active-low PWM drive: (fwd_power - rev_power)
        left_power = ((65535.0 - self.left_fwd_duty) - (65535.0 - self.left_rev_duty)) / 65535.0
        right_power = ((65535.0 - self.right_fwd_duty) - (65535.0 - self.right_rev_duty)) / 65535.0
        return left_power * self.max_wheel_speed_mms, right_power * self.max_wheel_speed_mms

    def step_physics(self, delta_time_seconds):
        left_speed, right_speed = self.compute_wheel_speeds()
        self.mouse.step(left_speed, right_speed, delta_time_seconds)
        self.elapsed_seconds += delta_time_seconds

    def read_adc(self, pin_id):
        sensor_role = self.adc_pin_map.get(pin_id, "front")
        return self.mouse.read_sensor_adc(sensor_role, self.segments)


simulation_engine = HardwareSimulation()


def set_sim_maze(maze_instance):
    simulation_engine.load_maze(maze_instance)


def get_mouse_state():
    return simulation_engine.mouse


def step_sim_physics(delta_time_seconds=config.SIM_TIMESTEP_S):
    simulation_engine.step_physics(delta_time_seconds)


def sim_time_ms():
    """Milliseconds of SIMULATED time since import, advanced only by stepping."""
    return int(simulation_engine.elapsed_seconds * 1000.0)

### Mock MicroPython machine classes ----------------------------------------------------------------

class Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, pin_id, mode=IN, pull=None):
        if isinstance(pin_id, int):
            self.id = pin_id
        else:
            self.id = 0
        self.mode = mode
        self.pull = pull
        if pull == Pin.PULL_UP:
            self._pin_value = 1
        else:
            self._pin_value = 0

    def value(self, val=None):
        if val is not None:
            self._pin_value = int(val)
            return self._pin_value
        return self._pin_value


class PWM:
    def __init__(self, pin):
        self.pin = pin
        self._frequency = 2000
        self._duty_cycle = 65535

    def freq(self, frequency_hz=None):
        if frequency_hz is not None:
            self._frequency = frequency_hz
        return self._frequency

    def duty_u16(self, duty_value=None):
        if duty_value is not None:
            self._duty_cycle = duty_value
            simulation_engine.set_motor_duty(self.pin.id, duty_value)
        return self._duty_cycle


class ADC:
    def __init__(self, pin_or_id):
        if isinstance(pin_or_id, Pin):
            self.id = pin_or_id.id
        elif isinstance(pin_or_id, int):
            self.id = pin_or_id
        else:
            self.id = 0

    def read_u16(self):
        return simulation_engine.read_adc(self.id)
