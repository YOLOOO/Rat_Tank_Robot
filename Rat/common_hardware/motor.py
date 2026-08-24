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

import time
from gpiozero import PWMOutputDevice
import atexit
import config

# --- Device handles (lazy — claimed on first use) ---
_m1p = None
_m1m = None
_m2p = None
_m2m = None

# Last commanded duty per track — used to detect a 0 -> moving transition,
# which is the only time a kickstart pulse is needed.
_m1_last = 0
_m2_last = 0


def _init():
    global _m1p, _m1m, _m2p, _m2m
    if _m1p is not None:
        return
    _m1p = PWMOutputDevice(config.MOTOR_LEFT_PLUS,   frequency=config.MOTOR_PWM_FREQ)
    _m1m = PWMOutputDevice(config.MOTOR_LEFT_MINUS,  frequency=config.MOTOR_PWM_FREQ)
    _m2p = PWMOutputDevice(config.MOTOR_RIGHT_PLUS,  frequency=config.MOTOR_PWM_FREQ)
    _m2m = PWMOutputDevice(config.MOTOR_RIGHT_MINUS, frequency=config.MOTOR_PWM_FREQ)


def _scale(value: int) -> float:
    """Clamp and scale -MAX_DUTY..MAX_DUTY to 0.0..1.0."""
    return max(0.0, min(1.0, abs(value) / config.MOTOR_MAX_DUTY))


def _set_motor(plus_dev, minus_dev, duty: int):
    """Drive one motor. Positive = physically backward, negative = physically
    forward, 0 = stop — the "+"/"-" pin labels are wiring, not direction; see
    set_motors()."""
    if duty > 0:
        minus_dev.value = 0
        plus_dev.value  = _scale(duty)
    elif duty < 0:
        plus_dev.value  = 0
        minus_dev.value = _scale(duty)
    else:
        plus_dev.value  = 0
        minus_dev.value = 0


def _needs_kickstart(last_duty: int, duty: int) -> bool:
    return last_duty == 0 and duty != 0 and _scale(duty) < config.MOTOR_KICKSTART_THRESHOLD


def _is_reversal(last_duty: int, duty: int) -> bool:
    return last_duty != 0 and duty != 0 and (last_duty > 0) != (duty > 0)


# --- Public API ---

def set_motors(left: int, right: int):
    """
    Drive both tracks independently.
    left, right : -4095 (full physically-forward) to +4095 (full physically-
    backward) — inverted from what the "+"/"-" pin naming suggests; verified
    against the real chassis via the manually-tuned remote_control.py key
    bindings (w/s), which pass raw MOTOR:left:right values straight through
    to this function.

    Two safety passes before the requested duty is actually applied:

    1. Reversal settle — plug-braking a spinning track straight into the
       opposite direction draws more current than starting from a stop.
       A track whose sign is flipping is forced to zero duty first and
       held there for MOTOR_REVERSAL_SETTLE_MS.
    2. Kickstart — a track starting from a dead stop at a low commanded
       duty may not have enough torque to overcome static friction (it can
       sustain motion at that duty once rolling, but never gets there), so
       it gets a brief kick toward MOTOR_KICKSTART_DUTY first.

    Both passes fire on both tracks together where needed, rather than one
    track at a time, so a straight command only pays each delay once.
    """
    global _m1_last, _m2_last
    _init()

    reversal_left  = _is_reversal(_m1_last, left)
    reversal_right = _is_reversal(_m2_last, right)

    if reversal_left or reversal_right:
        if reversal_left:
            _set_motor(_m1p, _m1m, 0)
            _m1_last = 0
        if reversal_right:
            _set_motor(_m2p, _m2m, 0)
            _m2_last = 0
        time.sleep(config.MOTOR_REVERSAL_SETTLE_MS / 1000.0)

    kick_left  = _needs_kickstart(_m1_last, left)
    kick_right = _needs_kickstart(_m2_last, right)

    if kick_left or kick_right:
        kick_duty = int(config.MOTOR_MAX_DUTY * config.MOTOR_KICKSTART_DUTY)
        if kick_left:
            _set_motor(_m1p, _m1m, kick_duty if left > 0 else -kick_duty)
        if kick_right:
            _set_motor(_m2p, _m2m, kick_duty if right > 0 else -kick_duty)
        time.sleep(config.MOTOR_KICKSTART_MS / 1000.0)

    _set_motor(_m1p, _m1m, left)
    _set_motor(_m2p, _m2m, right)
    _m1_last, _m2_last = left, right


def forward(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(-speed, -speed)


def backward(speed: int = config.MOTOR_SPEED_NORMAL):
    set_motors(speed, speed)


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
    if _m1p is None:
        return
    stop()
    _m1p.close()
    _m1m.close()
    _m2p.close()
    _m2m.close()


