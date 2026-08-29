"""behavior_scripts/servo/ramp.py

Non-blocking, time-interpolated servo move — the same math already proven
by motion_indication_test.py's self-test servo sweep, generalized so any
mission can drive a paced arm/grip move from its own per-tick run(brain)
without ever blocking that tick (unlike behavior_scripts/motor/turn_degree.py,
which sleeps and was deliberately left unwired from any mission for exactly
that reason).

Callers own all move state themselves — start angle, start time, duration —
as plain values in their own module globals, the same way AI_controlled.py
already tracks _motor_l/_motor_r and remote_control.py tracks _arm_angle/
_grip_angle. This module holds none.

Typical use, once per brain tick:
    _arm_angle, done = ramp.step('0', _arm_move_start_angle, _arm_target_angle,
                                  _arm_move_start_time, _arm_move_duration, brain)

...and on receiving a new command that (re)targets the move:
    _arm_move_start_angle = _arm_angle       # start from wherever we are now
    _arm_target_angle     = _ARM_UP_ANGLE
    _arm_move_duration    = ramp.duration_for(_arm_move_start_angle, _arm_target_angle, speed)
    _arm_move_start_time  = time.time()
"""

import time

import config
from behavior_scripts.utilities.check_halt import is_halted
from common_hardware import get_servo_controller

_FULL_SWEEP_S = {
    "SLOW": config.SERVO_MOVE_FULL_SWEEP_SLOW_S,
    "MID":  config.SERVO_MOVE_FULL_SWEEP_MID_S,
    "FAST": config.SERVO_MOVE_FULL_SWEEP_FAST_S,
}


def duration_for(start_angle: float, target_angle: float, speed: str) -> float:
    """Seconds the move should take, scaled by how far it's actually going —
    a small nudge at :SLOW doesn't take as long as a full-range sweep at
    :SLOW. Unknown speed strings fall back to config.SERVO_MOVE_DEFAULT_SPEED."""
    full_sweep_s = _FULL_SWEEP_S.get(speed, _FULL_SWEEP_S[config.SERVO_MOVE_DEFAULT_SPEED])
    return abs(target_angle - start_angle) / 180.0 * full_sweep_s


def step(channel, start_angle: float, target_angle: float, start_time: float,
         duration: float, brain=None):
    """
    Advances one tick's worth of a time-interpolated move from start_angle
    toward target_angle, and commands the servo to the interpolated angle.

    Call once per brain tick with the same (start_angle, target_angle,
    start_time, duration) throughout a single move. Returns (current_angle,
    done) — once done is True, stop calling this for that move (or start a
    new one with a fresh start_angle/start_time/duration).

    A no-op call (start_angle == target_angle already) returns immediately
    without touching the servo. Halted calls skip commanding the servo and
    return start_angle unchanged, done=False — the physical servo just
    holds its last position, same as a halted motor holding zero.
    """
    if target_angle == start_angle:
        return target_angle, True
    if is_halted(brain):
        return start_angle, False

    servo = get_servo_controller()

    if duration <= 0:
        servo.setServoPwm(str(channel), int(round(target_angle)))
        return target_angle, True

    elapsed = time.time() - start_time
    if elapsed >= duration:
        servo.setServoPwm(str(channel), int(round(target_angle)))
        return target_angle, True

    progress = elapsed / duration
    angle = start_angle + (target_angle - start_angle) * progress
    servo.setServoPwm(str(channel), int(round(angle)))
    return angle, False
