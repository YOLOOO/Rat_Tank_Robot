"""
missions/remote_control.py

Puts the robot under direct remote control via the MNT trackball.

Expects commands from the queue:
    MOTOR:left:right   — set motor speeds directly (-4095..+4095)
    ARM_TOGGLE         — raise/lower arm (servo ch0)
    GRIP_TOGGLE        — open/close grip (servo ch1)

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
_ARM_UP_ANGLE   = config.SERVO_CH0_MAX   # 150°
_ARM_DOWN_ANGLE = config.SERVO_CH0_MIN   # 90°

# Grip angles (servo ch1)
_GRIP_OPEN_ANGLE  = config.SERVO_CH1_MIN   # 90°
_GRIP_CLOSE_ANGLE = config.SERVO_CH1_MAX   # 150°


def run(brain) -> bool:
    """
    Called every brain tick while mission is active.
    Returns True to keep running, False on halt.
    """
    global _arm_is_up, _grip_is_open

    if is_halted(brain):
        stop(brain)
        return False

    command = brain.command_server.get_command(timeout=0)

    if command is None:
        return True

    if command.startswith("MOTOR:"):
        _handle_motor(command)

    elif command == "ARM_TOGGLE":
        servo = get_servo_controller()
        if _arm_is_up:
            servo.setServoPwm('0', _ARM_DOWN_ANGLE)
            _arm_is_up = False
            logger.debug("Arm down")
        else:
            servo.setServoPwm('0', _ARM_UP_ANGLE)
            _arm_is_up = True
            logger.debug("Arm up")

    elif command == "GRIP_TOGGLE":
        servo = get_servo_controller()
        if _grip_is_open:
            servo.setServoPwm('1', _GRIP_CLOSE_ANGLE)
            _grip_is_open = False
            logger.debug("Grip closed")
        else:
            servo.setServoPwm('1', _GRIP_OPEN_ANGLE)
            _grip_is_open = True
            logger.debug("Grip open")

    return True


def _handle_motor(command: str):
    try:
        _, left, right = command.split(":")
        motor.set_motors(int(left), int(right))
    except Exception as e:
        logger.error(f"Bad MOTOR command '{command}': {e}")
        motor.stop()
