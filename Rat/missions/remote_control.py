"""
missions/remote_control.py

Puts the robot under direct remote control via the keyboard.

Expects commands from the queue:
    MOTOR:left:right   — set motor speeds directly (-4095..+4095)
    ARM_TOGGLE         — raise/lower arm (servo ch0) to preset angles
    GRIP_TOGGLE        — open/close grip (servo ch1) to preset angles
    SERVO:ch:delta     — nudge servo ch (0=arm, 1=grip) by delta degrees

HALT is handled by brain before this mission ever sees it.
This mission runs indefinitely — the operator ends it by sending HALT.
"""

import logging

import common_hardware.motor as motor
from common_hardware import get_servo_controller
from behavior_scripts.motor.stop import run as stop
from behavior_scripts.utilities.check_halt import is_halted
import config

logger = logging.getLogger(__name__)

# Arm and grip toggle state — persists across ticks
_arm_is_up    = False
_grip_is_open = False

# Arm angles (servo ch0)
_ARM_UP_ANGLE   = config.SERVO_CH0_MAX
_ARM_DOWN_ANGLE = config.SERVO_CH0_MIN

# Grip angles (servo ch1)
_GRIP_OPEN_ANGLE  = config.SERVO_CH1_MIN
_GRIP_CLOSE_ANGLE = config.SERVO_CH1_MAX

# Tracked angles for fine servo control — start at down/closed positions
_arm_angle  = float(_ARM_DOWN_ANGLE)
_grip_angle = float(_GRIP_CLOSE_ANGLE)

# Set on first tick of each mission run — see run()
_initialized = False


def _servo_clamp(angle: float, ch_min: int, ch_max: int) -> int:
    lo = min(ch_min, ch_max)
    hi = max(ch_min, ch_max)
    return int(max(lo, min(hi, angle)))


def run(brain) -> bool:
    """
    Called every brain tick while mission is active.
    Returns True to keep running, False on halt.
    """
    global _arm_is_up, _grip_is_open, _arm_angle, _grip_angle, _initialized

    if is_halted(brain):
        stop(brain)
        return False

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
            _initialized = True
            logger.info("Remote control armed — arm parked down, grip closed")

        # Drain all queued commands per tick — prevents backlog when sender rate
        # exceeds brain tick rate (30 Hz sender vs 20 Hz brain)
        while True:
            command = brain.command_server.get_command(timeout=0)
            if command is None:
                break

            if command.startswith("MOTOR:"):
                _handle_motor(command)

            elif command == "ARM_TOGGLE":
                _handle_arm_toggle()

            elif command == "GRIP_TOGGLE":
                _handle_grip_toggle()

            elif command.startswith("SERVO:"):
                _handle_servo_fine(command)

    except Exception as e:
        # Never let a transient hardware hiccup take the whole session down —
        # that's what used to strand the operator: the brain would catch this
        # one level up, kill the mission, and drop into ERROR/IDLE, silently
        # ignoring every command after while the last-commanded servo held its
        # position ("stuck"). Log it, stop the motors for safety, and keep the
        # mission alive so the operator keeps getting responses.
        logger.error(f"Remote control tick error: {e}")
        motor.stop()

    return True


def _handle_motor(command: str):
    try:
        _, left, right = command.split(":")
        motor.set_motors(int(left), int(right))
    except Exception as e:
        logger.error(f"Bad MOTOR command '{command}': {e}")
        motor.stop()


def _handle_arm_toggle():
    global _arm_is_up, _arm_angle
    try:
        servo  = get_servo_controller()
        target = _ARM_DOWN_ANGLE if _arm_is_up else _ARM_UP_ANGLE
        servo.setServoPwm('0', target)
        _arm_angle = float(target)
        _arm_is_up = not _arm_is_up
        logger.debug(f"Arm {'up' if _arm_is_up else 'down'}")
    except Exception as e:
        logger.error(f"Arm toggle failed: {e}")


def _handle_grip_toggle():
    global _grip_is_open, _grip_angle
    try:
        servo  = get_servo_controller()
        target = _GRIP_CLOSE_ANGLE if _grip_is_open else _GRIP_OPEN_ANGLE
        servo.setServoPwm('1', target)
        _grip_angle   = float(target)
        _grip_is_open = not _grip_is_open
        logger.debug(f"Grip {'open' if _grip_is_open else 'closed'}")
    except Exception as e:
        logger.error(f"Grip toggle failed: {e}")


def _handle_servo_fine(command: str):
    global _arm_angle, _grip_angle
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
            logger.debug(f"Arm fine → {_arm_angle}°")

        elif ch == 1:
            _grip_angle = _servo_clamp(
                _grip_angle + delta,
                config.SERVO_CH1_MIN, config.SERVO_CH1_MAX,
            )
            servo.setServoPwm('1', _grip_angle)
            logger.debug(f"Grip fine → {_grip_angle}°")

    except Exception as e:
        logger.error(f"Bad SERVO command '{command}': {e}")
