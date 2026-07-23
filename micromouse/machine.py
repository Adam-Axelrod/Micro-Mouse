"""Mock MicroPython machine module for desktop PC simulation.

Provides synthetic Pin, PWM, and ADC classes that mirror MicroPython's C machine module.
Allows setup.py to run unchanged on both PC and Pico.
On PC, writing PWM duties updates the MouseState physics engine, and reading ADC returns
simulated phototransistor light intensity values via raycasting.
"""

import math
import config
from geometry import build_wall_segments
from maze import MazeStructure
from mouse import MouseState


class HardwareSimulation:
    def __init__(self):
        self.mouse = MouseState()
        self.maze = None
        self.segments = []
        self.left_motor_duty = 65535  # Active-low default (OFF)
        self.right_motor_duty = 65535
        self.max_wheel_speed_mms = 600.0  # mm/s at 100% duty

        self.adc_pin_map = {
            29: "left",
            28: "front",
            27: "front",
            26: "right",
        }

    def load_maze(self, maze_instance):
        self.maze = maze_instance
        self.segments = build_wall_segments(maze_instance)

    def set_motor_duty(self, pin_id, duty):
        if pin_id in (9, 3, 2, 7):
            self.left_motor_duty = duty
        elif pin_id in (17, 4, 5, 8):
            self.right_motor_duty = duty

    def duty_to_speed(self, duty):
        power_fraction = (65535 - duty) / 65535.0
        return power_fraction * self.max_wheel_speed_mms

    def step_physics(self, delta_time_seconds):
        left_speed = self.duty_to_speed(self.left_motor_duty)
        right_speed = self.duty_to_speed(self.right_motor_duty)
        self.mouse.step(left_speed, right_speed, delta_time_seconds)

    def read_adc(self, pin_id):
        sensor_role = self.adc_pin_map.get(pin_id, "front")
        return self.mouse.read_sensor_adc(sensor_role, self.segments)


simulation_engine = HardwareSimulation()


def set_sim_maze(maze_instance):
    simulation_engine.load_maze(maze_instance)


def get_mouse_state():
    return simulation_engine.mouse


def step_sim_physics(delta_time_seconds=0.01):
    simulation_engine.step_physics(delta_time_seconds)

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
