"""
missions/remote_control.py

Puts the robot under direct remote control via the MNT trackball.

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
_grip_angle = float(_GRIP_OPEN_ANGLE)


def _servo_clamp(angle: float, ch_min: int, ch_max: int) -> int:
    lo = min(ch_min, ch_max)
    hi = max(ch_min, ch_max)
    return int(max(lo, min(hi, angle)))


def run(brain) -> bool:
    """
    Called every brain tick while mission is active.
    Returns True to keep running, False on halt.
    """
    global _arm_is_up, _grip_is_open, _arm_angle, _grip_angle

    if is_halted(brain):
        stop(brain)
        return False

    # Drain all queued commands per tick — prevents backlog when sender rate
    # exceeds brain tick rate (30 Hz sender vs 20 Hz brain)
    while True:
        command = brain.command_server.get_command(timeout=0)
        if command is None:
            break

        if command.startswith("MOTOR:"):
            _handle_motor(command)

        elif command == "ARM_TOGGLE":
            servo = get_servo_controller()
            if _arm_is_up:
                servo.setServoPwm('0', _ARM_DOWN_ANGLE)
                _arm_angle = float(_ARM_DOWN_ANGLE)
                _arm_is_up = False
                logger.debug("Arm down")
            else:
                servo.setServoPwm('0', _ARM_UP_ANGLE)
                _arm_angle = float(_ARM_UP_ANGLE)
                _arm_is_up = True
                logger.debug("Arm up")

        elif command == "GRIP_TOGGLE":
            servo = get_servo_controller()
            if _grip_is_open:
                servo.setServoPwm('1', _GRIP_CLOSE_ANGLE)
                _grip_angle = float(_GRIP_CLOSE_ANGLE)
                _grip_is_open = False
                logger.debug("Grip closed")
            else:
                servo.setServoPwm('1', _GRIP_OPEN_ANGLE)
                _grip_angle = float(_GRIP_OPEN_ANGLE)
                _grip_is_open = True
                logger.debug("Grip open")

        elif command.startswith("SERVO:"):
            _handle_servo_fine(command)

    return True


def _handle_motor(command: str):
    try:
        _, left, right = command.split(":")
        motor.set_motors(int(left), int(right))
    except Exception as e:
        logger.error(f"Bad MOTOR command '{command}': {e}")
        motor.stop()


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
