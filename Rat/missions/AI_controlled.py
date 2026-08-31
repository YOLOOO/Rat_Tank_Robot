"""
missions/AI_controlled.py

Local-LLM-driven autonomous control. The robot streams sensor telemetry
(distance, IR, camera snapshots) to a client on the dev PC and executes
whatever AI_CMD:* action that client sends back each loop.

Command channel (dev PC -> robot, port config.SERVER_PORT) is the existing
one. This mission additionally opens a second, outbound connection
(robot -> dev PC, port config.AI_TELEMETRY_PORT) on a background thread to
push telemetry. The dev PC address is read from
brain.command_server.client_address — the IP of whoever is currently
connected on the command channel — so there is nothing to hardcode.

Expects commands from the queue, all prefixed AI_CMD: to avoid clashing
with other missions' command handlers:
    AI_CMD:FORWARD[:SLOW|:FAST]
    AI_CMD:BACKWARD[:SLOW|:FAST]
    AI_CMD:SPIN_LEFT
    AI_CMD:SPIN_RIGHT
    AI_CMD:CURVE:left:right
    AI_CMD:STOP
    AI_CMD:ARM_UP[:SLOW|:MID|:FAST] / AI_CMD:ARM_DOWN[:SLOW|:MID|:FAST]
    AI_CMD:GRIP_OPEN[:SLOW|:MID|:FAST] / AI_CMD:GRIP_CLOSE[:SLOW|:MID|:FAST]
                           — arm/grip moves are non-blocking and time-
                             interpolated (behavior_scripts/servo/ramp.py),
                             advanced by one tick's worth every run() call
                             regardless of new commands — see that module
                             and config.SERVO_MOVE_FULL_SWEEP_*_S. No
                             modifier defaults to config.SERVO_MOVE_DEFAULT_SPEED.
    AI_CMD:SNAPSHOT        — force an out-of-cycle camera capture
    AI_CMD:GOAL:dist_cm:ir:tolerance_cm:max_duration_s
                           — set/replace the mission's goal (see below).
                             Sent once by the client right after mission
                             select; -1 on dist_cm/ir means "no goal on
                             that axis", <=0 on max_duration_s means "no
                             timeout".

HALT is handled entirely by the brain before this mission ever sees it
(same model as remote_control), so run() always returns True on HALT.
Because this mission holds resources beyond a single tick (telemetry,
snapshot, ultrasonic, and LED threads, open sensor handles), on_stop() is
what the brain calls on HALT to tear them down — run() alone would never
get the chance.

Terminal statuses: besides running until HALT, this mission can end itself
via _complete(brain, status, reason) — sending one final telemetry payload
with a non-"RUNNING" status (GOAL_REACHED, STUCK, TIMEOUT, SENSOR_FAULT)
and returning False so the brain returns to IDLE cleanly. A pre-flight
sensor failure (before any of this is armed) is different: it raises
instead, so the brain drops into ERROR rather than quietly going back to
IDLE — see run()'s _initialized block.

Ultrasonic reads run on their own thread (get_distance() can bit-bang for
up to ~1s on a timeout — doing that synchronously on the main tick would
stall AI_CMD draining and HALT responsiveness). A separate LED thread
drives the 4-LED status ring: spinning while the dev PC is connected and
driving the robot, solid red if that connection drops or a tick just
errored. See _ultrasonic_loop() and _led_loop() below.
"""

import base64
import json
import logging
import socket
import subprocess
import threading
import time

from behavior_scripts.motor import forward as m_forward
from behavior_scripts.motor import backward as m_backward
from behavior_scripts.motor import spin_left as m_spin_left
from behavior_scripts.motor import spin_right as m_spin_right
from behavior_scripts.motor import curve_turn as m_curve
from behavior_scripts.motor import stop as m_stop
from behavior_scripts.servo import ramp as servo_ramp
from behavior_scripts.led import patterns as led_patterns
from common_hardware import get_servo_controller
from common_hardware.ultrasonic import Ultrasonic
from common_hardware.infrared import Infrared
import config

logger = logging.getLogger(__name__)

# Arm angles (servo ch0) — CH0_MIN is physically DOWN, CH0_MAX is UP.
_ARM_UP_ANGLE   = config.SERVO_CH0_MAX
_ARM_DOWN_ANGLE = config.SERVO_CH0_MIN

# Grip angles (servo ch1)
_GRIP_OPEN_ANGLE  = config.SERVO_CH1_MIN
_GRIP_CLOSE_ANGLE = config.SERVO_CH1_MAX

# --- Module-level state — reset on every reload (mission reselect) ---
# _generation guards against a stale background thread from a *previous*
# run() surviving into a new one. The brain restarts this mission via
# importlib.reload() on the same module object, so a HALT immediately
# followed by reselecting AI_CONTROLLED re-executes this file in the same
# namespace: an old thread that hasn't yet rechecked `_initialized` (e.g.
# the snapshot thread blocked up to 8s inside a capture) would otherwise
# see the *new* run()'s _initialized=True and keep going — two threads
# then drive the same GPIO pins / camera / socket at once. Each thread
# captures its own generation number as an argument at start time (not a
# global read), so a stale thread notices the mismatch and exits even
# though _initialized has flipped back to True for the new run.
_generation       = 0
_initialized      = False
_telemetry_thread = None
_telemetry_sock   = None
_telemetry_send_lock = threading.Lock()  # shared between _telemetry_loop and
                                          # _complete()'s synchronous final send
_snapshot_thread  = None
_led_thread       = None
_ultrasonic_thread = None
_ultrasonic       = None
_infrared         = None

_arm_up      = False
_grip_closed = True
_motor_l     = 0
_motor_r     = 0

# --- Servo move state (behavior_scripts/servo/ramp.py) — one in-progress
# (or just-completed) move per channel. _arm_angle/_grip_angle are the
# current tracked angle, updated every tick from ramp.step()'s return value;
# the _move_start_* fields are frozen for the duration of whichever move is
# active and only change when a new ARM_*/GRIP_* command retargets it. Set
# to the parked position on init — see run()'s _initialized block — and
# reset there again in on_stop().
_arm_angle             = 0.0
_arm_move_start_angle  = 0.0
_arm_target_angle      = 0.0
_arm_move_start_time   = 0.0
_arm_move_duration     = 0.0

_grip_angle            = 0.0
_grip_move_start_angle = 0.0
_grip_target_angle     = 0.0
_grip_move_start_time  = 0.0
_grip_move_duration    = 0.0

_last_tick_error_time = 0.0  # time.time() of the most recent tick exception

_dist_cm = -1
_ir_bits = 0

_last_frame_b64   = None
_last_camera_time = 0.0
_force_snapshot   = False

# --- Sensor-fault / stuck tracking ---
_dist_fault_since = None  # time.time() the ultrasonic started reading -1 continuously, or None
_ir_fault_since   = None  # time.time() infrared reads started raising continuously, or None
_blocked_since    = None  # time.time() the LLM started re-issuing a forward/curve move that
                           # keeps getting blocked by the onboard obstacle interlock, or None
_last_drive_cmd_time = None  # time.time() of the most recent FORWARD/BACKWARD/SPIN/CURVE
                              # AI_CMD, refreshed on receipt regardless of whether the obstacle
                              # interlock ends up blocking it — see AI_DRIVE_HOLD_S in config.py

# --- Goal system — set via AI_CMD:GOAL, evaluated every tick ---
_goal_dist_cm         = -1.0
_goal_ir              = -1
_goal_tolerance_cm    = config.AI_GOAL_TOLERANCE_CM
_goal_max_duration_s  = 0.0

# --- Terminal status reported over telemetry — see _complete() ---
_status        = "RUNNING"
_status_reason = ""


class _PreflightFailure(Exception):
    """Raised only out of the one-time pre-flight sensor check so run()'s
    general per-tick exception handler (which logs and keeps the mission
    alive) never swallows it — a dead sensor at startup must abort the
    mission into ERROR, not be treated like a transient tick hiccup."""


def _preflight_check(ultrasonic: Ultrasonic, infrared: Infrared):
    """A few quick back-to-back reads on both sensors before anything is
    armed. Only raises on a sensor that looks outright dead — never lets a
    silently-broken sensor pass as "just far away" or "no line detected".

    Infrared is only checked for read failures, not for a constant value
    across the burst: a robot sitting still over a non-reflective floor
    legitimately reads the same (all-zero) value every time, so "constant"
    isn't a reliable dead-sensor signal here and would just produce false
    aborts.
    """
    dist_readings = []
    for _ in range(config.AI_PREFLIGHT_READS):
        dist_readings.append(ultrasonic.get_distance())
    if all(d == -1 for d in dist_readings):
        raise _PreflightFailure(f"ultrasonic: all {config.AI_PREFLIGHT_READS} pre-flight reads failed ({dist_readings})")

    for _ in range(config.AI_PREFLIGHT_READS):
        try:
            infrared.read_all_infrared()
        except Exception as e:
            raise _PreflightFailure(f"infrared: pre-flight read raised {e!r}")


def run(brain) -> bool:
    global _initialized, _telemetry_thread, _snapshot_thread, _led_thread, _ultrasonic_thread
    global _ultrasonic, _infrared, _dist_cm, _ir_bits, _last_tick_error_time, _generation
    global _motor_l, _motor_r, _dist_fault_since, _ir_fault_since, _blocked_since, _last_drive_cmd_time
    global _arm_angle, _arm_move_start_angle, _arm_target_angle, _arm_move_start_time, _arm_move_duration
    global _grip_angle, _grip_move_start_angle, _grip_target_angle, _grip_move_start_time, _grip_move_duration

    try:
        if not _initialized:
            m_stop.run(brain)
            servo = get_servo_controller()
            servo.setServoPwm('0', _ARM_DOWN_ANGLE)
            servo.setServoPwm('1', _GRIP_CLOSE_ANGLE)
            # Instant park, not a ramped move — this is one-time hardware
            # arming, not a commanded ARM_*/GRIP_* action. Seed the move
            # state as "already there" so the first real command computes
            # its ramp distance from the actual parked angle.
            _arm_angle = _arm_move_start_angle = _arm_target_angle = float(_ARM_DOWN_ANGLE)
            _arm_move_start_time = 0.0
            _arm_move_duration   = 0.0
            _grip_angle = _grip_move_start_angle = _grip_target_angle = float(_GRIP_CLOSE_ANGLE)
            _grip_move_start_time = 0.0
            _grip_move_duration   = 0.0

            ultrasonic = Ultrasonic()
            infrared   = Infrared()
            try:
                _preflight_check(ultrasonic, infrared)
            except _PreflightFailure as e:
                logger.error(f"AI_CONTROLLED pre-flight FAILED — aborting without arming motors/threads: {e}")
                try:
                    ultrasonic.close()
                except Exception:
                    logger.exception("Ultrasonic close error during pre-flight abort")
                try:
                    infrared.close()
                except Exception:
                    logger.exception("Infrared close error during pre-flight abort")
                raise

            _ultrasonic = ultrasonic
            _infrared   = infrared
            _dist_fault_since = None
            _ir_fault_since   = None
            _blocked_since    = None
            _last_drive_cmd_time = None
            _initialized = True
            _generation += 1
            gen = _generation

            _telemetry_thread = threading.Thread(target=_telemetry_loop, args=(brain, gen), daemon=True)
            _telemetry_thread.start()

            if config.AI_CAMERA_RATE > 0:
                _snapshot_thread = threading.Thread(target=_snapshot_loop, args=(gen,), daemon=True)
                _snapshot_thread.start()

            # get_distance() bit-bangs the echo pin: ~50ms settle + up to 1s
            # busy-waiting for the echo edge on timeout. On the main tick
            # thread that stalls the whole 50ms brain loop for up to a full
            # second every single tick — starving AI_CMD draining and HALT
            # responsiveness. Off-thread, same pattern as the camera.
            #
            # The sensor instance is passed in rather than read from the
            # _ultrasonic global on every iteration, and this thread closes
            # it itself once its loop exits — see _ultrasonic_loop().
            # Otherwise a restart racing the old thread's teardown would
            # hand it a freshly-reassigned _ultrasonic instance to keep
            # reading from (two threads bit-banging the same pins), or
            # on_stop() could close the sensor's GPIO chip handle out from
            # under an in-flight read on this thread — GPIO handles, unlike
            # sockets, aren't safe to close cross-thread while in use.
            _ultrasonic_thread = threading.Thread(target=_ultrasonic_loop, args=(_ultrasonic, gen), daemon=True)
            _ultrasonic_thread.start()

            _led_thread = threading.Thread(target=_led_loop, args=(brain, gen), daemon=True)
            _led_thread.start()

            logger.info("AI_CONTROLLED armed — arm parked down, grip closed, telemetry starting")

        try:
            _ir_bits = _infrared.read_all_infrared()
            _ir_fault_since = None
        except Exception:
            logger.exception("Infrared read error")
            if _ir_fault_since is None:
                _ir_fault_since = time.time()
            elif time.time() - _ir_fault_since > config.AI_SENSOR_FAULT_TIMEOUT_S:
                return _complete(brain, "SENSOR_FAULT",
                                  f"infrared reads failing for >{config.AI_SENSOR_FAULT_TIMEOUT_S}s")

        # Continuous version of the pre-flight check: _dist_cm == -1 already
        # makes _obstacle_ahead() fail closed (treated as "obstacle") on
        # every single bad read, which is the right instant reaction — but a
        # sensor that's actually dead rather than momentarily noisy should
        # end the mission instead of quietly treating "always -1" as "always
        # blocked forever".
        if _dist_cm == -1:
            if _dist_fault_since is None:
                _dist_fault_since = time.time()
            elif time.time() - _dist_fault_since > config.AI_SENSOR_FAULT_TIMEOUT_S:
                return _complete(brain, "SENSOR_FAULT",
                                  f"ultrasonic stuck at error/-1 for >{config.AI_SENSOR_FAULT_TIMEOUT_S}s")
        else:
            _dist_fault_since = None

        # Hard onboard safety interlock — independent of whatever the dev-PC
        # LLM loop decided. AI_CMD commands persist across ticks (the LLM
        # only reconsiders once every AI_LOOP_RATE, often 1s+ with a cold
        # local model), so without this a FORWARD/CURVE issued before an
        # obstacle closed in keeps executing every 50ms tick until the next
        # LLM response arrives — which at MOTOR_SPEED_FAST can be well after
        # impact. Runs every tick regardless of whether a new command came
        # in, using the live _dist_cm the ultrasonic thread just updated.
        if _obstacle_ahead() and _nets_forward(_motor_l, _motor_r):
            logger.warning(f"Onboard safety: dist_cm={_dist_cm} — stopping forward motion")
            m_stop.run(brain)
            _motor_l = _motor_r = 0

        # Stale-drive-command interlock — a second, independent cap on how
        # long a FORWARD/BACKWARD/SPIN/CURVE command can keep the tracks
        # moving without a fresh AI_CMD refreshing it (see AI_DRIVE_HOLD_S).
        # Distinct from the obstacle interlock above: this fires with a
        # perfectly clear path too, any time the dev-PC's next decision is
        # simply slow to arrive (a cold or vision-model Ollama call can take
        # many seconds — well past AI_LOOP_RATE), turning every drive
        # command into a short, bounded burst rather than open-loop
        # dead-reckoning for however long that call happens to take.
        if (_motor_l != 0 or _motor_r != 0) and _last_drive_cmd_time is not None \
                and (time.time() - _last_drive_cmd_time) > config.AI_DRIVE_HOLD_S:
            logger.info(f"Drive command stale (>{config.AI_DRIVE_HOLD_S}s) — holding for next decision")
            m_stop.run(brain)
            _motor_l = _motor_r = 0

        # Advance any in-progress arm/grip ramp by one tick's worth — runs
        # every tick regardless of whether a new AI_CMD came in, same as the
        # obstacle interlock above. A no-op (single comparison, no servo
        # write) once a move is already complete.
        _arm_angle, _  = servo_ramp.step('0', _arm_move_start_angle, _arm_target_angle,
                                          _arm_move_start_time, _arm_move_duration, brain)
        _grip_angle, _ = servo_ramp.step('1', _grip_move_start_angle, _grip_target_angle,
                                          _grip_move_start_time, _grip_move_duration, brain)

        # Drain all queued commands per tick, same pattern as remote_control.
        while True:
            command = brain.command_server.get_command(timeout=0)
            if command is None:
                break
            if command.startswith("AI_CMD:"):
                _dispatch(command, brain)

        if _goal_reached():
            return _complete(brain, "GOAL_REACHED", f"dist_cm={_dist_cm} ir={_ir_bits}")

        if _blocked_since is not None and (time.time() - _blocked_since) > config.AI_STUCK_TIMEOUT_S:
            return _complete(brain, "STUCK",
                              f"forward motion blocked by obstacle for >{config.AI_STUCK_TIMEOUT_S}s")

        if _goal_max_duration_s > 0 and brain.mission_start_time is not None:
            elapsed = time.time() - brain.mission_start_time
            if elapsed > _goal_max_duration_s:
                return _complete(brain, "TIMEOUT", f"exceeded max_duration_s={_goal_max_duration_s}")

    except _PreflightFailure:
        raise
    except Exception:
        logger.exception("AI_controlled tick error")
        _last_tick_error_time = time.time()
        m_stop.run(brain)

    return True


def on_stop(brain):
    """Called by the brain when the mission is stopped (HALT). run() gets
    no further ticks after this, so this is the only place background
    threads and open sensor handles can be released."""
    global _initialized, _telemetry_sock, _ultrasonic, _infrared
    global _arm_up, _grip_closed, _motor_l, _motor_r
    global _arm_angle, _arm_move_start_angle, _arm_target_angle, _arm_move_start_time, _arm_move_duration
    global _grip_angle, _grip_move_start_angle, _grip_target_angle, _grip_move_start_time, _grip_move_duration
    global _last_frame_b64, _last_camera_time, _force_snapshot, _last_tick_error_time
    global _dist_fault_since, _ir_fault_since, _blocked_since, _last_drive_cmd_time
    global _goal_dist_cm, _goal_ir, _goal_tolerance_cm, _goal_max_duration_s
    global _status, _status_reason

    _initialized = False  # signals telemetry/snapshot/LED/ultrasonic threads to exit

    # _telemetry_sock is closed here (main thread) while _telemetry_loop
    # (background thread) may be mid-sendall() on the same socket object.
    # Unlike the ultrasonic GPIO handle below, this is safe: sendall()
    # already holds its own reference to the socket object, so a close()
    # here can at worst make that in-flight send raise — which
    # _telemetry_loop already catches, logs, and treats as "reconnect".
    # There's no window where it can corrupt another mission run's state.
    if _telemetry_sock is not None:
        try:
            _telemetry_sock.close()
        except Exception:
            pass
        _telemetry_sock = None

    # Not closed here: _ultrasonic_loop() owns the sensor it was started
    # with and closes it itself once its own loop exits, since a raw GPIO
    # chip handle isn't safe to close from this (main) thread while that
    # background thread may still be mid bit-bang read on it. Just drop our
    # reference — a restart creates a brand new Ultrasonic() anyway.
    _ultrasonic = None

    if _infrared is not None:
        try:
            _infrared.close()
        except Exception:
            logger.exception("Infrared close error")
        _infrared = None

    _arm_up            = False
    _grip_closed        = True
    _motor_l = _motor_r = 0
    # Servo move state resets to the parked position — matches what the
    # next run()'s _initialized block will physically re-park the hardware
    # to, so a fresh move's ramp distance is computed correctly from the
    # start rather than from wherever the last run happened to leave off.
    _arm_angle = _arm_move_start_angle = _arm_target_angle = float(_ARM_DOWN_ANGLE)
    _arm_move_start_time = 0.0
    _arm_move_duration   = 0.0
    _grip_angle = _grip_move_start_angle = _grip_target_angle = float(_GRIP_CLOSE_ANGLE)
    _grip_move_start_time = 0.0
    _grip_move_duration   = 0.0
    _last_frame_b64     = None
    _last_camera_time   = 0.0
    _force_snapshot      = False
    _last_tick_error_time = 0.0
    _dist_fault_since   = None
    _ir_fault_since     = None
    _blocked_since      = None
    _last_drive_cmd_time = None
    _goal_dist_cm        = -1.0
    _goal_ir             = -1
    _goal_tolerance_cm   = config.AI_GOAL_TOLERANCE_CM
    _goal_max_duration_s = 0.0
    _status        = "RUNNING"
    _status_reason = ""

    logger.info("AI_CONTROLLED stopped — sensors and telemetry closed")


# ----------------------------------------------------------------------------
# Command dispatch
# ----------------------------------------------------------------------------

def _obstacle_ahead() -> bool:
    """Same rule as the dev-PC client's _apply_safety, evaluated here too
    against the live reading so it isn't at the mercy of the LLM loop's
    slower cadence or a command type the client-side check doesn't cover."""
    return _dist_cm == -1 or (0 <= _dist_cm < config.AI_MIN_OBSTACLE_CM)


def _goal_reached() -> bool:
    """True once the currently-configured goal (set via AI_CMD:GOAL) is
    satisfied. With no goal configured on either axis this always returns
    False — the mission then just runs until HALT/STUCK/TIMEOUT/
    SENSOR_FAULT, same as before the goal system existed. With both axes
    configured, both must be satisfied simultaneously."""
    has_dist_goal = _goal_dist_cm >= 0
    has_ir_goal   = _goal_ir >= 0
    if not has_dist_goal and not has_ir_goal:
        return False

    dist_ok = (not has_dist_goal) or (_dist_cm != -1 and abs(_dist_cm - _goal_dist_cm) <= _goal_tolerance_cm)
    ir_ok   = (not has_ir_goal) or (_ir_bits == _goal_ir)
    return dist_ok and ir_ok


def _send_telemetry_now():
    """Send one telemetry payload immediately over whatever socket
    _telemetry_loop currently holds. Used by _complete() so the dev PC is
    guaranteed to see the terminal status/reason — waiting on the normal
    AI_TELEMETRY_RATE-paced loop would race on_stop() tearing the thread
    down right after run() returns False."""
    if _telemetry_sock is None:
        return
    try:
        with _telemetry_send_lock:
            payload = _build_telemetry(last_sent_frame_time=float("inf"))  # never attach a frame — keep this send fast
            _telemetry_sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    except Exception:
        logger.warning("Final telemetry send failed")


def _complete(brain, status: str, reason: str) -> bool:
    """End the mission on a terminal condition — GOAL_REACHED, STUCK,
    TIMEOUT, or SENSOR_FAULT — instead of running until HALT. Stops the
    motors, reports the status/reason to the dev PC over telemetry (so the
    client sees why the mission ended instead of just losing the
    connection), and returns False so the brain returns to IDLE and calls
    on_stop() to tear everything down. Always call this as `return
    _complete(...)` from inside run()."""
    global _status, _status_reason
    m_stop.run(brain)
    logger.warning(f"AI_CONTROLLED completing: status={status} reason={reason}")
    _status        = status
    _status_reason = reason
    _send_telemetry_now()
    return False


def _nets_forward(left: int, right: int) -> bool:
    """True if left+right nets physically forward (negative — see motor.py).
    Using the sum rather than "either track negative" means a symmetric
    spin (e.g. SPIN_LEFT's -speed/+speed) nets to zero and isn't treated as
    driving into whatever's ahead — turning in place near an obstacle is
    exactly how the robot is supposed to get away from it."""
    return (left + right) < 0


def _speed_for_modifier(parts) -> int:
    if len(parts) == 3:
        if parts[2] == "SLOW":
            return config.MOTOR_SPEED_SLOW
        if parts[2] == "FAST":
            return config.MOTOR_SPEED_FAST
    return config.MOTOR_SPEED_NORMAL


def _servo_speed_for_modifier(parts) -> str:
    if len(parts) == 3 and parts[2] in ("SLOW", "MID", "FAST"):
        return parts[2]
    return config.SERVO_MOVE_DEFAULT_SPEED


def _dispatch(command: str, brain):
    global _motor_l, _motor_r, _arm_up, _grip_closed, _force_snapshot, _blocked_since, _last_drive_cmd_time
    global _goal_dist_cm, _goal_ir, _goal_tolerance_cm, _goal_max_duration_s
    global _arm_move_start_angle, _arm_target_angle, _arm_move_start_time, _arm_move_duration
    global _grip_move_start_angle, _grip_target_angle, _grip_move_start_time, _grip_move_duration

    # Set below only by the FORWARD/CURVE branches when this specific
    # dispatch got blocked by the obstacle interlock. Any other outcome —
    # including a FORWARD/CURVE that wasn't blocked — clears the "stuck"
    # clock: it only keeps ticking while the LLM keeps re-trying the same
    # blocked forward move tick after tick. See _blocked_since's declaration.
    blocked_this_command = False

    try:
        parts  = command.split(":")
        action = parts[1]

        # Refresh the stale-drive-command clock on receipt, regardless of
        # whether the obstacle interlock below ends up blocking it — a
        # blocked-but-received command is still a fresh decision from the
        # LLM, just not one that's allowed to move right now. See
        # AI_DRIVE_HOLD_S in config.py and run()'s interlock.
        if action in ("FORWARD", "BACKWARD", "SPIN_LEFT", "SPIN_RIGHT", "CURVE"):
            _last_drive_cmd_time = time.time()

        if action == "FORWARD":
            if _obstacle_ahead():
                logger.warning(f"Onboard safety: dist_cm={_dist_cm} — blocking FORWARD")
                m_stop.run(brain)
                _motor_l = _motor_r = 0
                blocked_this_command = True
            else:
                speed = _speed_for_modifier(parts)
                # _motor_l/_motor_r track actual raw duty sent to set_motors()
                # (negative = physically forward — see motor.py), not the
                # command's semantic sign, so telemetry and the obstacle
                # checks below agree with CURVE's raw values too. Only
                # recorded if the wrapper actually issued the command — a
                # HALT racing in mid-dispatch (m_forward.run() returns
                # False) must not leave telemetry claiming motion that was
                # never sent; the brain stops the motors for real on its
                # very next tick regardless.
                if m_forward.run(speed, brain):
                    _motor_l = _motor_r = -speed
                else:
                    _motor_l = _motor_r = 0

        elif action == "BACKWARD":
            speed = _speed_for_modifier(parts)
            if m_backward.run(speed, brain):
                _motor_l = _motor_r = speed
            else:
                _motor_l = _motor_r = 0

        elif action == "SPIN_LEFT":
            if m_spin_left.run(config.MOTOR_SPEED_NORMAL, brain):
                _motor_l, _motor_r = -config.MOTOR_SPEED_NORMAL, config.MOTOR_SPEED_NORMAL
            else:
                _motor_l = _motor_r = 0

        elif action == "SPIN_RIGHT":
            if m_spin_right.run(config.MOTOR_SPEED_NORMAL, brain):
                _motor_l, _motor_r = config.MOTOR_SPEED_NORMAL, -config.MOTOR_SPEED_NORMAL
            else:
                _motor_l = _motor_r = 0

        elif action == "CURVE":
            left, right = int(parts[2]), int(parts[3])
            if _obstacle_ahead() and _nets_forward(left, right):
                logger.warning(f"Onboard safety: dist_cm={_dist_cm} — blocking forward CURVE:{left}:{right}")
                m_stop.run(brain)
                _motor_l = _motor_r = 0
                blocked_this_command = True
            else:
                if m_curve.run(left, right, brain):
                    _motor_l, _motor_r = left, right
                else:
                    _motor_l = _motor_r = 0

        elif action == "STOP":
            m_stop.run(brain)
            _motor_l = _motor_r = 0

        elif action == "ARM_UP":
            # Retargets the ramp the next tick's servo_ramp.step() advances —
            # see run(). Starting from _arm_angle (wherever the arm actually
            # is right now, not the previous move's nominal target) means a
            # command that arrives mid-move smoothly redirects instead of
            # jumping back to where the last move started.
            speed = _servo_speed_for_modifier(parts)
            _arm_move_start_angle = _arm_angle
            _arm_target_angle     = _ARM_UP_ANGLE
            _arm_move_duration    = servo_ramp.duration_for(_arm_move_start_angle, _arm_target_angle, speed)
            _arm_move_start_time  = time.time()
            _arm_up = True

        elif action == "ARM_DOWN":
            speed = _servo_speed_for_modifier(parts)
            _arm_move_start_angle = _arm_angle
            _arm_target_angle     = _ARM_DOWN_ANGLE
            _arm_move_duration    = servo_ramp.duration_for(_arm_move_start_angle, _arm_target_angle, speed)
            _arm_move_start_time  = time.time()
            _arm_up = False

        elif action == "GRIP_OPEN":
            speed = _servo_speed_for_modifier(parts)
            _grip_move_start_angle = _grip_angle
            _grip_target_angle     = _GRIP_OPEN_ANGLE
            _grip_move_duration    = servo_ramp.duration_for(_grip_move_start_angle, _grip_target_angle, speed)
            _grip_move_start_time  = time.time()
            _grip_closed = False

        elif action == "GRIP_CLOSE":
            speed = _servo_speed_for_modifier(parts)
            _grip_move_start_angle = _grip_angle
            _grip_target_angle     = _GRIP_CLOSE_ANGLE
            _grip_move_duration    = servo_ramp.duration_for(_grip_move_start_angle, _grip_target_angle, speed)
            _grip_move_start_time  = time.time()
            _grip_closed = True

        elif action == "SNAPSHOT":
            _force_snapshot = True

        elif action == "GOAL":
            _goal_dist_cm        = float(parts[2])
            _goal_ir             = int(parts[3])
            _goal_tolerance_cm   = float(parts[4])
            _goal_max_duration_s = float(parts[5])
            logger.info(
                f"Goal set: dist_cm={_goal_dist_cm} ir={_goal_ir} "
                f"tolerance_cm={_goal_tolerance_cm} max_duration_s={_goal_max_duration_s}"
            )

        else:
            logger.warning(f"Unknown AI_CMD action: {command}")

    except Exception:
        logger.exception(f"Bad AI_CMD '{command}'")
        m_stop.run(brain)

    finally:
        if blocked_this_command:
            if _blocked_since is None:
                _blocked_since = time.time()
        else:
            _blocked_since = None


# ----------------------------------------------------------------------------
# Telemetry thread — robot connects out to whoever holds the command channel
# ----------------------------------------------------------------------------

def _build_telemetry(last_sent_frame_time: float) -> dict:
    ir0 = (_ir_bits >> 2) & 1
    ir1 = (_ir_bits >> 1) & 1
    ir2 = _ir_bits & 1

    payload = {
        "t":       time.time(),
        "dist_cm": _dist_cm,
        "ir":      [ir0, ir1, ir2],
        "motor_l": _motor_l,
        "motor_r": _motor_r,
        "arm":     "up" if _arm_up else "down",
        "grip":    "closed" if _grip_closed else "open",
        # "RUNNING" for every regular tick; one final payload carries the
        # terminal status/reason set by _complete() right before the mission
        # stops itself — see module docstring.
        "status":  _status,
        "reason":  _status_reason,
    }
    # Only attach the frame once, the tick after it was captured — sending
    # the same JPEG on every 5Hz telemetry tick would multiply bandwidth for
    # no benefit since the dev PC only samples it periodically anyway.
    if _last_frame_b64 and _last_camera_time > last_sent_frame_time:
        payload["frame_b64"] = _last_frame_b64
    return payload


def _telemetry_loop(brain, gen):
    global _telemetry_sock

    last_sent_frame_time = 0.0
    connected_ip = None  # IP the current _telemetry_sock is actually connected to

    while _initialized and _generation == gen:
        dev_pc_ip = getattr(brain.command_server, "client_address", None)

        # A new controller connecting (reconnect, NAT rebind, client
        # restart) changes client_address without ever breaking this
        # thread's existing outbound socket at the TCP layer — sendall() to
        # the old peer can keep "succeeding" for a while. Reconnect as soon
        # as the IP diverges instead of waiting for a send to eventually
        # fail or time out.
        if _telemetry_sock is not None and dev_pc_ip != connected_ip:
            logger.info(f"Controller IP changed ({connected_ip} -> {dev_pc_ip}) — reconnecting telemetry")
            try:
                _telemetry_sock.close()
            except Exception:
                pass
            _telemetry_sock = None
            connected_ip = None

        if _telemetry_sock is None:
            if not dev_pc_ip:
                time.sleep(1.0)
                continue
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((dev_pc_ip, config.AI_TELEMETRY_PORT))
                _telemetry_sock = sock
                connected_ip = dev_pc_ip
                logger.info(f"Telemetry connected to {dev_pc_ip}:{config.AI_TELEMETRY_PORT}")
            except Exception as e:
                logger.warning(f"Telemetry connect to {dev_pc_ip} failed: {e}")
                time.sleep(2.0)
                continue

        try:
            with _telemetry_send_lock:
                payload = _build_telemetry(last_sent_frame_time)
                if "frame_b64" in payload:
                    last_sent_frame_time = _last_camera_time
                _telemetry_sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        except Exception:
            logger.warning("Telemetry send failed — reconnecting")
            try:
                _telemetry_sock.close()
            except Exception:
                pass
            _telemetry_sock = None
            connected_ip = None

        time.sleep(config.AI_TELEMETRY_RATE)


# ----------------------------------------------------------------------------
# Ultrasonic thread — get_distance() self-paces (settle time + up to a 1s
# echo timeout), so this loop just calls it back-to-back with a tiny floor
# sleep to avoid pegging the CPU on the rare fast-return case.
# ----------------------------------------------------------------------------

def _ultrasonic_loop(ultrasonic, gen):
    global _dist_cm

    while _initialized and _generation == gen:
        _dist_cm = ultrasonic.get_distance()
        time.sleep(0.02)

    try:
        ultrasonic.close()
    except Exception:
        logger.exception("Ultrasonic close error")


# ----------------------------------------------------------------------------
# LED thread — status indicator for the AI session
# ----------------------------------------------------------------------------

def _led_loop(brain, gen):
    """Spins one LED at a time around the 4-LED ring to show the robot is
    under active dev-PC/LLM control — which is most of the mission, since
    AI_CMD commands are persistent and the robot is otherwise just waiting
    on the next one. Switches to solid LED_COLOR_DISCONNECTED whenever that
    control is gone: either the command connection to the dev PC has dropped
    (brain.command_server.client_address goes None — the client crashed, was
    Ctrl-C'd without a clean HALT, or the network dropped) or a tick just
    raised. Both look identical from the robot's side — "the AI stopped
    driving me" — and are worth surfacing at a glance instead of only in the
    log. Kept visually distinct from the brain's own LED_COLOR_ERROR so a
    solid ring doesn't conflate "AI lost its dev-PC link" with "brain itself
    faulted".
    """
    spin_start = time.time()
    while _initialized and _generation == gen:
        disconnected = brain.command_server.client_address is None
        crashed = (time.time() - _last_tick_error_time) < config.AI_UNRESPONSIVE_WINDOW

        if disconnected or crashed:
            led_patterns.static(config.LED_COLOR_DISCONNECTED)
        else:
            led_patterns.step_spin(config.LED_COLOR_CONNECTED, config.AI_LED_SPIN_INTERVAL, spin_start)

        time.sleep(config.AI_LED_SPIN_INTERVAL)


# ----------------------------------------------------------------------------
# Snapshot thread — runs rpicam-still out-of-band so a ~300ms+ capture never
# stalls the main brain tick (which also has to stay responsive to HALT).
# Matches the capture approach already proven in missions/camera_test.py.
# ----------------------------------------------------------------------------

def _capture_jpeg():
    width, height = config.AI_CAMERA_SIZE
    try:
        proc = subprocess.Popen(
            [
                "rpicam-still", "-n", "-t", str(config.AI_CAMERA_WARMUP_MS),
                "--rotation", str(config.AI_CAMERA_ROTATION_DEG),
                "--width", str(width), "--height", str(height),
                "-q", str(config.AI_CAMERA_JPEG_QUALITY),
                "-o", "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            # SIGTERM first, same escalation as camera_test.py's stream
            # cleanup and stop_rat.sh — gives rpicam-still's own libcamera
            # teardown a chance to release the camera device cleanly. A
            # bare SIGKILL (what subprocess.run's timeout path uses) skips
            # that teardown entirely and can leave the device claimed,
            # breaking every capture after this one until something else
            # frees it.
            logger.warning("Snapshot capture timed out — terminating")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logger.warning("rpicam-still did not terminate — killing")
                proc.kill()
                proc.wait()
            return None

        if proc.returncode != 0 or not stdout:
            logger.warning(f"Snapshot capture failed: {stderr.decode(errors='replace')}")
            return None
        return stdout
    except FileNotFoundError:
        logger.error("rpicam-still not found — camera snapshots disabled")
        return None
    except Exception:
        logger.exception("Snapshot capture error")
        return None


def _snapshot_loop(gen):
    global _last_frame_b64, _last_camera_time, _force_snapshot

    while _initialized and _generation == gen:
        due = _force_snapshot or (time.time() - _last_camera_time) >= config.AI_CAMERA_RATE
        if due:
            frame = _capture_jpeg()
            if frame:
                _last_frame_b64 = base64.b64encode(frame).decode("ascii")
            _last_camera_time = time.time()
            _force_snapshot = False
        time.sleep(0.1)
