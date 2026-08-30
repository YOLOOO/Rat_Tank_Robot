"""
missions/motion_indication_test.py

Hardware test mission — cycles through LED, Servo, and Motor checks.
Called each brain tick via run(brain). Returns False when all phases complete.

Motor API  : behavior_scripts.motor.set_motors.run(left, right, brain)
LED API    : behavior_scripts.led.patterns             →  patterns.step_blend(color_a, color_b, ...), patterns.off()
Servo API  : get_servo_controller()                 →  servo.setServoPwm('0', angle)
"""

import logging
import time

from behavior_scripts.motor import set_motors as m_set_motors
from behavior_scripts.motor import spin_left as m_spin_left
from behavior_scripts.motor import spin_right as m_spin_right
from behavior_scripts.motor import stop as m_stop
from behavior_scripts.led import patterns as led_patterns
from common_hardware import get_servo_controller

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — reset each time the mission is started
# ---------------------------------------------------------------------------
_phase       = 0       # 0=LED  1=SERVO  2=MOTOR
_step        = 0
_phase_start = 0.0
_initialized = False


def _reset():
    global _phase, _step, _phase_start, _initialized
    _phase       = 0
    _step        = 0
    _phase_start = time.time()
    _initialized = True


# ---------------------------------------------------------------------------
# LED phase — fade through colours, _LED_BLEND_S seconds per transition
# ---------------------------------------------------------------------------
_LED_COLORS = [
    (255, 0,   0,   "Red"),
    (0,   255, 0,   "Green"),
    (0,   0,   255, "Blue"),
    (255, 255, 255, "White"),
    (255, 255, 0,   "Yellow"),
    (0,   255, 255, "Cyan"),
    (255, 0,   255, "Magenta"),
]

_LED_BLEND_S = 1.0  # seconds to fade from one color to the next


def _run_led_phase() -> bool:
    """Returns True while still running, False when done. Fades from each
    color to the next via led_patterns.step_blend() — each segment ends
    exactly at the halfway point of its triangle wave (period = 2x the
    segment length), so only the color_a -> color_b half is ever reached;
    the wave never gets a chance to fade back before the segment advances."""
    global _step, _phase_start

    if _step >= len(_LED_COLORS) - 1:
        led_patterns.off()
        logger.info("LED phase complete")
        return False

    color_a = _LED_COLORS[_step][:3]
    name_b  = _LED_COLORS[_step + 1][3]
    color_b = _LED_COLORS[_step + 1][:3]
    elapsed = time.time() - _phase_start

    if elapsed >= _LED_BLEND_S:
        _step       += 1
        _phase_start = time.time()
        logger.debug(f"LED: reached {name_b}")
    else:
        led_patterns.step_blend(color_a, color_b, _LED_BLEND_S * 2, _phase_start)

    return True


# ---------------------------------------------------------------------------
# Servo phase — sweep ch0 and ch1 back and forth using config limits
# ---------------------------------------------------------------------------
# Seconds per degree — increase to slow down, decrease to speed up
_SERVO_STEP_DELAY = 0.03  # 30ms per degree → ~60° sweep takes ~1.8s

def _servo_moves():
    """Build move list from config limits so calibrated values are always used."""
    ch0_min = config.SERVO_CH0_MIN
    ch0_max = config.SERVO_CH0_MAX
    ch1_min = config.SERVO_CH1_MIN
    ch1_max = config.SERVO_CH1_MAX
    return [
        (1, ch1_min, ch1_min),   # ensure grip open (arm starts at min/down)
        (0, ch0_min, ch0_max),   # arm: up
        (1, ch1_min, ch1_max),   # grip: open → close  (arm is up)
        (1, ch1_max, ch1_min),   # grip: close → open  (arm is up, grip open before arm descends)
        (0, ch0_max, ch0_min),   # arm: down  (grip is open)
        (0, ch0_min, ch0_max),   # arm: up  (park up)
        (1, ch1_min, ch1_max),   # grip: close  (park closed, arm is up)
    ]


def _run_servo_phase() -> bool:
    global _step, _phase_start

    servo  = get_servo_controller()
    moves  = _servo_moves()

    if _step >= len(moves):
        logger.info("Servo phase complete")
        return False

    channel, start, end = moves[_step]
    sweep_duration = abs(end - start) * _SERVO_STEP_DELAY

    elapsed = time.time() - _phase_start

    if elapsed >= sweep_duration:
        servo.setServoPwm(str(channel), end)
        logger.debug(f"Servo {channel}: {start}°→{end}°")
        _step       += 1
        _phase_start = time.time()
    else:
        progress = elapsed / sweep_duration if sweep_duration > 0 else 1.0
        angle    = int(start + (end - start) * progress)
        servo.setServoPwm(str(channel), angle)

    return True


# ---------------------------------------------------------------------------
# Motor phase — brief movement sequences
# ---------------------------------------------------------------------------
_MOTOR_MOVES = [
    ("Forward",      lambda brain: m_set_motors.run( config.MOTOR_SPEED_NORMAL,  config.MOTOR_SPEED_NORMAL, brain),  2.0),
    ("Backward",     lambda brain: m_set_motors.run(-config.MOTOR_SPEED_NORMAL, -config.MOTOR_SPEED_NORMAL, brain),  2.0),
    ("Spin left",    lambda brain: m_spin_left.run(config.MOTOR_SPEED_NORMAL, brain),                                2.0),
    ("Spin right",   lambda brain: m_spin_right.run(config.MOTOR_SPEED_NORMAL, brain),                               2.0),
    ("Curve left",   lambda brain: m_set_motors.run( config.MOTOR_SPEED_SLOW,    config.MOTOR_SPEED_NORMAL, brain),  1.5),
    ("Curve right",  lambda brain: m_set_motors.run( config.MOTOR_SPEED_NORMAL,  config.MOTOR_SPEED_SLOW, brain),    1.5),
    ("Stop",         lambda brain: m_stop.run(brain),                                                                0.5),
]


def _run_motor_phase(brain) -> bool:
    global _step, _phase_start

    if _step >= len(_MOTOR_MOVES):
        m_stop.run(brain)
        logger.info("Motor phase complete")
        return False

    name, func, duration = _MOTOR_MOVES[_step]
    elapsed = time.time() - _phase_start

    if elapsed < duration:
        func(brain)
        logger.debug(f"Motor: {name}")
    else:
        _step       += 1
        _phase_start = time.time()

    return True


# ---------------------------------------------------------------------------
# Mission entry point
# ---------------------------------------------------------------------------

def run(brain) -> bool:
    """
    Called every brain tick while this mission is active.
    Returns True to keep running, False to finish and return to IDLE.
    """
    global _phase, _step, _phase_start, _initialized

    if not _initialized:
        _reset()
        logger.info("Hardware test mission started")

    try:
        if _phase == 0:
            if not _run_led_phase():
                _phase       = 1
                _step        = 0
                _phase_start = time.time()

        elif _phase == 1:
            if not _run_servo_phase():
                # Explicitly park arm up before motor phase so movement doesn't swing it
                try:
                    servo = get_servo_controller()
                    servo.setServoPwm('0', config.SERVO_CH0_MAX)
                except Exception:
                    logger.exception("Arm park error")
                _phase       = 2
                _step        = 0
                _phase_start = time.time()

        elif _phase == 2:
            if not _run_motor_phase(brain):
                logger.info("All hardware tests complete")
                _initialized = False
                return False

        return True

    except Exception:
        logger.exception("Test mission error")
        m_stop.run(brain)
        _initialized = False
        return False
