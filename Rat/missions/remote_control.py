"""
missions/remote_control.py

Puts the robot under direct remote control via the keyboard.

Expects commands from the queue:
    MOTOR:left:right   — set motor speeds directly (-4095..+4095)
    ARM_TOGGLE         — raise/lower arm (servo ch0) to preset angles,
                         time-interpolated at _TOGGLE_SPEED via
                         behavior_scripts/servo/ramp.py (non-blocking)
    GRIP_TOGGLE        — open/close grip (servo ch1) to preset angles, same ramp
    SERVO:ch:delta     — nudge servo ch (0=arm, 1=grip) by delta degrees, instant

HALT is handled by brain before this mission ever sees it.
This mission runs indefinitely — the operator ends it by sending HALT.
"""

import logging
import time

from behavior_scripts.motor import set_motors as m_set_motors
from behavior_scripts.motor import stop as m_stop
from behavior_scripts.servo import ramp as servo_ramp
from common_hardware import get_servo_controller
import config

logger = logging.getLogger(__name__)

# ARM_TOGGLE/GRIP_TOGGLE always ramp at this tier for now — no speed-modifier
# keybinding exists on the dev-PC client yet (see MOTOR_SENSORY_REWORK_2026-08-29
# follow-up note). Easy to make configurable per-keypress later.
_TOGGLE_SPEED = "MID"

# Arm and grip toggle state — persists across ticks
_arm_is_up    = False
_grip_is_open = False

# Arm angles (servo ch0)
_ARM_UP_ANGLE   = config.SERVO_CH0_MAX
_ARM_DOWN_ANGLE = config.SERVO_CH0_MIN

# Grip angles (servo ch1)
_GRIP_OPEN_ANGLE  = config.SERVO_CH1_MIN
_GRIP_CLOSE_ANGLE = config.SERVO_CH1_MAX

# Current tracked angle per channel, updated every tick from ramp.step()'s
# return value (ARM_TOGGLE/GRIP_TOGGLE) or directly (SERVO: fine nudge) —
# start at down/closed positions.
_arm_angle  = float(_ARM_DOWN_ANGLE)
_grip_angle = float(_GRIP_CLOSE_ANGLE)

# In-progress (or just-completed) ramp move per channel — see
# behavior_scripts/servo/ramp.py. start==target is the "no move in flight"
# state ramp.step() treats as an immediate no-op.
_arm_move_start_angle  = float(_ARM_DOWN_ANGLE)
_arm_target_angle      = float(_ARM_DOWN_ANGLE)
_arm_move_start_time   = 0.0
_arm_move_duration     = 0.0

_grip_move_start_angle = float(_GRIP_CLOSE_ANGLE)
_grip_target_angle     = float(_GRIP_CLOSE_ANGLE)
_grip_move_start_time  = 0.0
_grip_move_duration    = 0.0

# Set on first tick of each mission run — see run()
_initialized = False


def _servo_clamp(angle: float, ch_min: int, ch_max: int) -> int:
    lo = min(ch_min, ch_max)
    hi = max(ch_min, ch_max)
    return int(max(lo, min(hi, angle)))


def run(brain) -> bool:
    """
    Called every brain tick while mission is active.
    HALT is handled entirely by the brain before this is ever called again,
    so this always returns True — the brain is what ends the mission.
    """
    global _arm_is_up, _grip_is_open, _arm_angle, _grip_angle, _initialized
    global _arm_move_start_angle, _arm_target_angle, _arm_move_start_time, _arm_move_duration
    global _grip_move_start_angle, _grip_target_angle, _grip_move_start_time, _grip_move_duration

    try:
        if not _initialized:
            # The mission module is reloaded (state reset to the down/closed
            # defaults above) every time this mission is (re)selected, but the
            # physical servo is left wherever the last session parked it. Without
            # this explicit sync, the first ARM_TOGGLE/GRIP_TOGGLE can command the
            # servo to the position it's already in — a silent no-op that still
            # logs normally.
            servo = get_servo_controller()
            servo.setServoPwm('0', _ARM_DOWN_ANGLE)
            servo.setServoPwm('1', _GRIP_CLOSE_ANGLE)
            # Instant park, not a ramped move — seed the ramp state as
            # "already there" so the first real ARM_TOGGLE/GRIP_TOGGLE
            # computes its move distance from the actual parked angle.
            _arm_angle = _arm_move_start_angle = _arm_target_angle = float(_ARM_DOWN_ANGLE)
            _arm_move_start_time = 0.0
            _arm_move_duration   = 0.0
            _grip_angle = _grip_move_start_angle = _grip_target_angle = float(_GRIP_CLOSE_ANGLE)
            _grip_move_start_time = 0.0
            _grip_move_duration   = 0.0
            _initialized = True
            logger.info("Remote control armed — arm parked down, grip closed")

        # Advance any in-progress arm/grip ramp by one tick's worth — runs
        # every tick regardless of whether a new toggle came in, same
        # pattern as AI_controlled.py. A no-op (single comparison, no servo
        # write) once a move is already complete.
        _arm_angle, _  = servo_ramp.step('0', _arm_move_start_angle, _arm_target_angle,
                                          _arm_move_start_time, _arm_move_duration, brain)
        _grip_angle, _ = servo_ramp.step('1', _grip_move_start_angle, _grip_target_angle,
                                          _grip_move_start_time, _grip_move_duration, brain)

        # Drain all queued commands per tick — prevents backlog when sender rate
        # exceeds brain tick rate (30 Hz sender vs 20 Hz brain)
        while True:
            command = brain.command_server.get_command(timeout=0)
            if command is None:
                break

            if command.startswith("MOTOR:"):
                _handle_motor(command, brain)

            elif command == "ARM_TOGGLE":
                _handle_arm_toggle()

            elif command == "GRIP_TOGGLE":
                _handle_grip_toggle()

            elif command.startswith("SERVO:"):
                _handle_servo_fine(command)

    except Exception:
        # Never let a transient hardware hiccup take the whole session down —
        # that's what used to strand the operator: the brain would catch this
        # one level up, kill the mission, and drop into ERROR/IDLE, silently
        # ignoring every command after while the last-commanded servo held its
        # position ("stuck"). Log it, stop the motors for safety, and keep the
        # mission alive so the operator keeps getting responses.
        logger.exception("Remote control tick error")
        m_stop.run(brain)

    return True


def _handle_motor(command: str, brain):
    try:
        _, left, right = command.split(":")
        m_set_motors.run(int(left), int(right), brain)
    except Exception:
        logger.exception(f"Bad MOTOR command '{command}'")
        m_stop.run(brain)


def _handle_arm_toggle():
    # Retargets the ramp the next tick's servo_ramp.step() advances — see
    # run(). Starting from _arm_angle (wherever the arm actually is right
    # now, not the previous move's nominal target) means a toggle that
    # arrives mid-move smoothly redirects instead of jumping back to where
    # the last move started.
    global _arm_is_up, _arm_move_start_angle, _arm_target_angle, _arm_move_start_time, _arm_move_duration
    try:
        target = _ARM_DOWN_ANGLE if _arm_is_up else _ARM_UP_ANGLE
        _arm_move_start_angle = _arm_angle
        _arm_target_angle     = float(target)
        _arm_move_duration    = servo_ramp.duration_for(_arm_move_start_angle, _arm_target_angle, _TOGGLE_SPEED)
        _arm_move_start_time  = time.time()
        _arm_is_up = not _arm_is_up
        logger.debug(f"Arm {'up' if _arm_is_up else 'down'}")
    except Exception:
        logger.exception("Arm toggle failed")


def _handle_grip_toggle():
    global _grip_is_open, _grip_move_start_angle, _grip_target_angle, _grip_move_start_time, _grip_move_duration
    try:
        target = _GRIP_CLOSE_ANGLE if _grip_is_open else _GRIP_OPEN_ANGLE
        _grip_move_start_angle = _grip_angle
        _grip_target_angle     = float(target)
        _grip_move_duration    = servo_ramp.duration_for(_grip_move_start_angle, _grip_target_angle, _TOGGLE_SPEED)
        _grip_move_start_time  = time.time()
        _grip_is_open = not _grip_is_open
        logger.debug(f"Grip {'open' if _grip_is_open else 'closed'}")
    except Exception:
        logger.exception("Grip toggle failed")


def _handle_servo_fine(command: str):
    # Instant, not ramped — this is a small manual nudge, not a toggle sweep.
    # Also cancels any in-flight ARM_TOGGLE/GRIP_TOGGLE ramp on that channel
    # (start==target marks "no move in flight" for ramp.step()'s next-tick
    # no-op check) so the ramp doesn't overwrite this nudge on the next tick.
    global _arm_angle, _grip_angle
    global _arm_move_start_angle, _arm_target_angle
    global _grip_move_start_angle, _grip_target_angle
    try:
        _, ch, delta = command.split(":")
        ch    = int(ch)
        delta = int(delta)
        servo = get_servo_controller()

        if ch == 0:
            _arm_angle = _servo_clamp(
                _arm_angle + delta,
                config.SERVO_CH0_MIN, config.SERVO_CH0_MAX,
            )
            servo.setServoPwm('0', _arm_angle)
            _arm_move_start_angle = _arm_target_angle = float(_arm_angle)
            logger.debug(f"Arm fine → {_arm_angle}°")

        elif ch == 1:
            _grip_angle = _servo_clamp(
                _grip_angle + delta,
                config.SERVO_CH1_MIN, config.SERVO_CH1_MAX,
            )
            servo.setServoPwm('1', _grip_angle)
            _grip_move_start_angle = _grip_target_angle = float(_grip_angle)
            logger.debug(f"Grip fine → {_grip_angle}°")

    except Exception:
        logger.exception(f"Bad SERVO command '{command}'")
