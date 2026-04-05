"""
common_hardware/motor.py

Motor driver for Freenove Tank FNK0077 V2.0 on Raspberry Pi 5.
Uses gpiozero with lgpio backend — the only reliable GPIO approach on Pi 5.

Hardware:
    M1 (left track) : GPIO23 (+), GPIO24 (-)
    M2 (right track) : GPIO6  (+), GPIO5  (-)

Duty range exposed to the rest of the system: -4095 to +4095
Internally scaled to 0.0–1.0 for gpiozero PWMOutputDevice.
"""

import os
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"

from gpiozero import PWMOutputDevice
import atexit
import config

# --- Device handles ---
_m1p = PWMOutputDevice(config.MOTOR_LEFT_PLUS,   frequency=config.MOTOR_PWM_FREQ)
_m1m = PWMOutputDevice(config.MOTOR_LEFT_MINUS,  frequency=config.MOTOR_PWM_FREQ)
_m2p = PWMOutputDevice(config.MOTOR_RIGHT_PLUS,  frequency=config.MOTOR_PWM_FREQ)
_m2m = PWMOutputDevice(config.MOTOR_RIGHT_MINUS, frequency=config.MOTOR_PWM_FREQ)


def _scale(value: int) -> float:
    """Clamp and scale -MAX_DUTY..MAX_DUTY to 0.0..1.0."""
    return max(0.0, min(1.0, abs(value) / config.MOTOR_MAX_DUTY))


def _set_motor(plus_dev, minus_dev, duty: int):
    """Drive one motor. Positive = forward, negative = backward, 0 = stop."""
    if duty > 0:
        minus_dev.value = 0
        plus_dev.value  = _scale(duty)
    elif duty < 0:
        plus_dev.value  = 0
        minus_dev.value = _scale(duty)
    else:
        plus_dev.value  = 0
        minus_dev.value = 0


# --- Public API ---

def set_motors(left: int, right: int):
    """
    Drive both tracks independently.
    left, right : -4095 (full reverse) to +4095 (full forward)
    """
    _set_motor(_m1p, _m1m, left)
    _set_motor(_m2p, _m2m, right)


def forward(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(speed, speed)


def backward(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(-speed, -speed)


def spin_left(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(-speed, speed)


def spin_right(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(speed, -speed)


def curve(left: int, right: int):
    """Arbitrary left/right mix for curves."""
    set_motors(left, right)


def stop():
    set_motors(0, 0)


def cleanup():
    stop()
    _m1p.close()
    _m1m.close()
    _m2p.close()
    _m2m.close()


atexit.register(cleanup)
