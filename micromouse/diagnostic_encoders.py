"""Quadrature encoder counter class for Raspberry Pi Pico RP2040 using PIO.

Uses a PIO state machine to decode quadrature encoder signals from motor shaft encoders.
Hardcoded pin assignments match the Gemini board wiring: left motor = pins 8/9, right motor = pins 6/7.
"""

import array
import machine
from machine import Pin
import rp2
import utime


class PIOQuadratureCounter:
    @rp2.asm_pio(autopush=False, autopull=False)
    def counter():
        jmp("update")        # 00 -> 00
        jmp("decrement")     # 00 -> 01
        jmp("increment")     # 00 -> 10
        jmp("update")        # 00 -> 11

        jmp("increment")     # 01 -> 00
        jmp("update")        # 01 -> 01
        jmp("update")        # 01 -> 10
        jmp("decrement")     # 01 -> 11

        jmp("decrement")     # 10 -> 00
        jmp("update")        # 10 -> 01
        jmp("update")        # 10 -> 10
        jmp("increment")     # 10 -> 11

        jmp("update")        # 11 -> 00
        jmp("increment")     # 11 -> 01
        label("decrement")   # 11 -> 10
        jmp(y_dec, "update")
        label("update")      # 11 -> 11

        wrap_target()
        set(x, 0)
        pull(noblock)        # Check for request

        mov(x, osr)
        mov(osr, isr)        # OSR = previous pins
        jmp(not_x, "sample_pins")

        # Report data
        mov(isr, y)
        push()

        label("sample_pins")
        mov(isr, null)
        in_(osr, 2)
        in_(pins, 2)
        mov(pc, isr)         # Jump to <previous>:<current>

        label("increment")
        mov(x, invert(y))
        jmp(x_dec, "increment2")
        label("increment2")
        mov(y, invert(x))
        wrap()
        nop()                # Fill program space for MicroPython PIO alignment
        nop()
        nop()

    def __init__(self, pio_state_machine_id, pin_a, pin_b):
        if pin_b != pin_a + 1:
            raise ValueError("pin_b must be pin_a + 1")

        Pin(pin_a, Pin.IN, Pin.PULL_UP)
        Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.state_machine = rp2.StateMachine(
            pio_state_machine_id, self.counter, freq=125000000, in_base=machine.Pin(pin_a)
        )
        self.state_machine.active(1)
        self.buffer = array.array("i", [0])

    def read(self):
        self.state_machine.put(1)
        self.state_machine.get(self.buffer)
        return self.buffer[0]


class Encoders:
    def __init__(self):
        self.left_counter = PIOQuadratureCounter(0, 8, 9)
        self.right_counter = PIOQuadratureCounter(1, 6, 7)

        self.left_offset = 0
        self.right_offset = 0
        self.get_counts(reset=True)

    def get_counts(self, reset=False):
        left_count = -self.left_counter.read() - self.left_offset
        right_count = self.right_counter.read() - self.right_offset

        if reset:
            self.left_offset += left_count
            self.right_offset += right_count

        return left_count, right_count
