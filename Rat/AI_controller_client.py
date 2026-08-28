"""
AI_controller_client.py (DEV PC)
=================================
Local-LLM control loop for the Rat tank robot. Selects the AI_CONTROLLED
mission on the robot, receives its telemetry (distance, IR, camera
snapshots) over a second TCP channel, feeds it to an Ollama model each
loop tick, and sends back one AI_CMD: action.

Usage:
    python AI_controller_client.py --host 192.168.0.237 --task "navigate toward the nearest wall and stop 20cm away from it"
    python AI_controller_client.py --host 192.168.0.237 --goal-distance-cm 20 --goal-tolerance-cm 3 --max-duration-s 120

Ctrl-C sends HALT to the robot before exiting. The robot can also end the
mission on its own — GOAL_REACHED, STUCK, TIMEOUT, or SENSOR_FAULT, reported
over telemetry's "status"/"reason" fields — in which case this process exits
0 for GOAL_REACHED and 1 for anything else.

Requires: pip install requests   (not in requirements.txt — that file is
robot-only GPIO libs; do not install it on the dev PC.)
"""

import argparse
import json
import logging
import signal
import socket
import sys
import threading
import time
from collections import deque

import requests

import config

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

_VISION_NAME_HINTS = ("llava", "moondream", "bakllava")

_VALID_ACTIONS = {
    "FORWARD", "FORWARD:SLOW", "FORWARD:FAST",
    "BACKWARD", "BACKWARD:SLOW", "BACKWARD:FAST",
    "SPIN_LEFT", "SPIN_RIGHT",
    "STOP", "ARM_UP", "ARM_DOWN", "GRIP_OPEN", "GRIP_CLOSE", "SNAPSHOT",
}

SYSTEM_PROMPT_TEMPLATE = """You are the brain of a small tracked robot (tank-style, two independent tracks).
You receive sensor readings every second and must respond with exactly one action.

ROBOT CAPABILITIES
- Two tracks: independent speed control
- Front ultrasonic sensor: measures forward distance
- Three infrared sensors under the chassis: left / center / right (1=line detected)
- One arm (up/down) and one gripper (open/closed)

AVAILABLE ACTIONS (respond with exactly one, nothing else):
  FORWARD         move forward at normal speed
  FORWARD:SLOW    move forward slowly
  FORWARD:FAST    move forward fast
  BACKWARD        move backward at normal speed
  BACKWARD:SLOW   move backward slowly
  SPIN_LEFT       rotate left in place
  SPIN_RIGHT      rotate right in place
  CURVE:L:R       fine control — L=left track, R=right track, each -4095 to 4095
                  (negative = that track drives forward, positive = backward,
                  same convention as motor_l/motor_r below)
  STOP            stop all motors
  ARM_UP          raise the arm
  ARM_DOWN        lower the arm
  GRIP_OPEN       open the gripper
  GRIP_CLOSE      close the gripper

SAFETY RULES:
- If dist_cm < 10, do NOT move forward.
- If dist_cm = -1 (sensor error), treat as obstacle at 5cm.
- Never send anything other than an action keyword. No explanation.

TASK: {task}

RECENT HISTORY (oldest first):
{history}

CURRENT STATE:
  dist_cm : {dist_cm}
  ir      : left={ir0}  center={ir1}  right={ir2}
  arm     : {arm}
  grip    : {grip}
  motors  : L={motor_l}  R={motor_r}
{image_line}

Respond with one action:"""

# Appended to image_line only when a frame is actually attached — gives the
# vision model something concrete to look for instead of just receiving a
# picture with no instructions. The numeric dist_cm above is ground truth
# for distance (the camera is for identifying what's ahead / the target
# object, not for judging range).
VISION_INSTRUCTION = (
    " — look for obstacles in your path and anything matching the TASK's "
    "target; use dist_cm above as the actual distance, not your visual guess"
)

# ------------------------------------------------------------------
# Telemetry server (robot -> dev PC)
# ------------------------------------------------------------------

class TelemetryServer:
    """Accepts the robot's outbound telemetry connection and keeps the
    most recently received JSON payload available to the control loop."""

    def __init__(self, port: int):
        self.port      = port
        self._latest   = None
        self._lock     = threading.Lock()
        self._sock     = None
        self._running  = False

    def start(self):
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.listen(1)
            self._sock.settimeout(1.0)
            logger.info(f"Telemetry server listening on 0.0.0.0:{self.port}")

            while self._running:
                try:
                    conn, addr = self._sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                logger.info(f"Robot telemetry connected from {addr}")
                threading.Thread(target=self._read_loop, args=(conn,), daemon=True).start()
        except Exception:
            logger.exception("Telemetry server error")

    def _read_loop(self, conn: socket.socket):
        buffer = ""
        conn.settimeout(5.0)
        try:
            while self._running:
                try:
                    data = conn.recv(65536).decode("utf-8")
                except socket.timeout:
                    continue
                if not data:
                    break
                buffer += data
                lines  = buffer.split("\n")
                buffer = lines[-1]
                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    with self._lock:
                        self._latest = payload
        except Exception:
            logger.exception("Telemetry read error")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            logger.info("Robot telemetry disconnected")

    def latest(self) -> dict:
        with self._lock:
            return self._latest

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass


# ------------------------------------------------------------------
# Robot command connection (dev PC -> robot)
# ------------------------------------------------------------------

def _connect_robot(host: str, port: int):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.settimeout(3.0)
        logger.info(f"Connected to robot at {host}:{port}")
        return sock
    except Exception as e:
        logger.error(f"Connection to robot failed: {e}")
        return None


_send_lock = threading.Lock()


def _send(sock: socket.socket, command: str) -> bool:
    try:
        with _send_lock:
            sock.send(f"{command}\n".encode("utf-8"))
        logger.debug(f"Sent: {command}")
        return True
    except Exception as e:
        logger.error(f"Send failed: {e}")
        return False


def _heartbeat_loop(sock: socket.socket, stop_event: threading.Event):
    """Keeps the command socket from going idle while a single Ollama call
    runs long — the robot drops the connection after CLIENT_IDLE_TIMEOUT
    (15s) of silence, and a cold-loading or vision model can easily take
    longer than that to answer one prompt. A blank line is enough: the
    robot's receiver updates its idle clock on any bytes received, and an
    empty command line is a no-op there."""
    while not stop_event.wait(config.AI_HEARTBEAT_INTERVAL):
        _send(sock, "")


def _select_ai_mission(sock: socket.socket):
    """Navigate the robot's IDLE menu to AI_CONTROLLED and select it.
    Assumes the robot is freshly at IDLE with selection_index 0 — same
    assumption controller_sender_client.py already makes for its menu
    tracking, since the brain doesn't expose current selection state."""
    menu   = sorted(config.MISSIONS.keys(), key=lambda n: config.MISSIONS[n][2])
    target = menu.index("AI_CONTROLLED")
    logger.info(f"Selecting AI_CONTROLLED (menu position {target}) — assumes robot is at IDLE, item 0")
    for _ in range(target):
        _send(sock, "RIGHT")
        time.sleep(0.1)
    _send(sock, "SELECT")
    time.sleep(0.2)


# ------------------------------------------------------------------
# Ollama
# ------------------------------------------------------------------

def _detect_vision(model: str) -> bool:
    name = model.lower()
    if any(hint in name for hint in _VISION_NAME_HINTS):
        return True
    try:
        resp = requests.post(f"{config.AI_OLLAMA_HOST}/api/show", json={"name": model}, timeout=5)
        resp.raise_for_status()
        families = resp.json().get("details", {}).get("families") or []
        return any("vision" in str(f).lower() for f in families)
    except Exception:
        return False


def _call_ollama(model: str, prompt: str, frame_b64, vision: bool) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    has_image = bool(frame_b64 and vision)
    if has_image:
        payload["images"] = [frame_b64]
    started = time.time()
    resp = requests.post(f"{config.AI_OLLAMA_HOST}/api/generate", json=payload, timeout=config.AI_OLLAMA_TIMEOUT)
    resp.raise_for_status()
    # Real round-trip time, logged every call rather than measured once —
    # vision calls (has_image=True) are the ones most likely to blow past
    # AI_LOOP_RATE, and cold/thermal-throttled behavior drifts over a
    # session, so a one-time measurement wouldn't stay representative.
    elapsed = time.time() - started
    level = logger.warning if elapsed > config.AI_LOOP_RATE else logger.debug
    level(f"Ollama call took {elapsed:.2f}s (image={has_image})")
    return resp.json().get("response", "").strip()


def _parse_action(raw: str):
    """LLMs often wrap the action in punctuation or stray text — scan
    line by line for something that matches the known vocabulary."""
    for line in raw.strip().upper().splitlines():
        candidate = line.strip().strip(".")
        if candidate in _VALID_ACTIONS:
            return candidate
        if candidate.startswith("CURVE:"):
            parts = candidate.split(":")
            if len(parts) == 3:
                try:
                    int(parts[1])
                    int(parts[2])
                    return candidate
                except ValueError:
                    pass
    return None


def _apply_safety(action: str, snap: dict) -> str:
    """Local models are unreliable about obeying numeric rules in the
    prompt — enforce the no-forward-into-an-obstacle rule client-side too.
    Covers CURVE as well as FORWARD: a CURVE with either track commanded
    positive still drives the robot toward whatever is ahead. This is a
    second line of defense — the robot's own onboard interlock in
    AI_controlled.py is the one that actually matters, since it reacts
    every ~50ms tick on the live sensor reading instead of waiting for the
    next LLM decision."""
    dist     = snap.get("dist_cm", -1)
    obstacle = dist == -1 or (0 <= dist < config.AI_MIN_OBSTACLE_CM)
    if not obstacle:
        return action
    if action == "FORWARD" or action.startswith("FORWARD:"):
        logger.warning(f"Safety override: dist_cm={dist} — blocking FORWARD, sending STOP instead")
        return "STOP"
    if action.startswith("CURVE:"):
        _, left, right = action.split(":")
        # Negative duty is physically forward (see motor.py) — a symmetric
        # spin (e.g. -x/+x) nets to zero and isn't treated as driving into
        # whatever's ahead, matching AI_controlled.py's onboard interlock.
        if int(left) + int(right) < 0:
            logger.warning(f"Safety override: dist_cm={dist} — blocking forward CURVE:{left}:{right}, sending STOP instead")
            return "STOP"
    return action


def _format_history(history) -> str:
    if not history:
        return "  (none yet)"
    lines = []
    for snap, action in history:
        lines.append(f"  [state: dist={snap.get('dist_cm')} ir={snap.get('ir')}] -> {action}")
    return "\n".join(lines)


def _build_prompt(task: str, history, snap: dict, vision: bool) -> str:
    ir = snap.get("ir") or [0, 0, 0]
    frame_b64  = snap.get("frame_b64")
    image_line = f"  camera  : [image attached]{VISION_INSTRUCTION}" if (frame_b64 and vision) else ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        task=task,
        history=_format_history(history),
        dist_cm=snap.get("dist_cm"),
        ir0=ir[0], ir1=ir[1], ir2=ir[2],
        arm=snap.get("arm"),
        grip=snap.get("grip"),
        motor_l=snap.get("motor_l"),
        motor_r=snap.get("motor_r"),
        image_line=image_line,
    )


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

def _send_goal(sock: socket.socket, args) -> None:
    """AI_CMD:GOAL:dist_cm:ir:tolerance_cm:max_duration_s — sent once right
    after mission select. -1 on dist_cm/ir means "no goal on that axis"; the
    robot evaluates this every tick and reports GOAL_REACHED/STUCK/TIMEOUT/
    SENSOR_FAULT back over telemetry (see missions/AI_controlled.py)."""
    goal_dist = args.goal_distance_cm if args.goal_distance_cm is not None else -1
    goal_ir   = args.goal_ir if args.goal_ir is not None else -1
    _send(sock, f"AI_CMD:GOAL:{goal_dist}:{goal_ir}:{args.goal_tolerance_cm}:{args.max_duration_s}")
    logger.info(
        f"Goal sent: goal_distance_cm={args.goal_distance_cm} goal_ir={args.goal_ir} "
        f"tolerance_cm={args.goal_tolerance_cm} max_duration_s={args.max_duration_s}"
    )


def main():
    parser = argparse.ArgumentParser(description="Local-LLM control loop for the Rat tank robot")
    parser.add_argument("--host", default=config.ROBOT_IP, help="Robot IP address")
    parser.add_argument("--task", default=config.AI_DEFAULT_TASK, help="Natural-language task for the LLM")
    parser.add_argument("--model", default=config.AI_DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--loop-rate", type=float, default=config.AI_LOOP_RATE, help="Seconds between LLM calls")
    parser.add_argument("--goal-distance-cm", type=float, default=config.AI_GOAL_DISTANCE_CM,
                         help="Stop once within --goal-tolerance-cm of this distance (default: no distance goal)")
    parser.add_argument("--goal-ir", type=int, default=config.AI_GOAL_IR, choices=range(0, 8), metavar="0-7",
                         help="Stop once the IR bitmask (left<<2|center<<1|right) reads exactly this (default: no IR goal)")
    parser.add_argument("--goal-tolerance-cm", type=float, default=config.AI_GOAL_TOLERANCE_CM,
                         help="Tolerance in cm for --goal-distance-cm")
    parser.add_argument("--max-duration-s", type=float, default=config.AI_MAX_DURATION_S,
                         help="Abort with TIMEOUT after this many seconds (default: 0 = disabled)")
    args = parser.parse_args()

    telemetry = TelemetryServer(config.AI_TELEMETRY_PORT)
    telemetry.start()

    robot_sock = _connect_robot(args.host, config.SERVER_PORT)
    if robot_sock is None:
        logger.error(f"Could not connect to robot at {args.host}:{config.SERVER_PORT}")
        sys.exit(1)

    _select_ai_mission(robot_sock)
    _send_goal(robot_sock, args)

    vision = _detect_vision(args.model)
    logger.info(f"Model '{args.model}' vision={vision}")

    history   = deque(maxlen=config.AI_COMMAND_HISTORY)
    stop_event = threading.Event()
    exit_code  = 0

    def _shutdown(*_):
        if stop_event.is_set():
            return
        stop_event.set()
        logger.warning("Shutting down — sending HALT")
        _send(robot_sock, "HALT")
        telemetry.stop()

    signal.signal(signal.SIGINT, _shutdown)

    threading.Thread(target=_heartbeat_loop, args=(robot_sock, stop_event), daemon=True).start()

    logger.info(f"AI control loop started — task: {args.task!r}")
    try:
        while not stop_event.is_set():
            snap = telemetry.latest()
            if snap is None:
                time.sleep(0.2)
                continue

            status = snap.get("status", "RUNNING")
            if status != "RUNNING":
                reason = snap.get("reason", "")
                exit_code = 0 if status == "GOAL_REACHED" else 1
                logger.info(f"Mission ended: status={status} reason={reason!r} — exiting {exit_code}")
                break

            prompt = _build_prompt(args.task, history, snap, vision)
            frame_b64 = snap.get("frame_b64") if vision else None

            try:
                raw = _call_ollama(args.model, prompt, frame_b64, vision)
            except Exception:
                # Vision calls are decision-relevant now, not just descriptive
                # — continuing on whatever the robot's last AI_CMD happened to
                # be (its only option, since nothing new arrived) risks
                # driving blind on a stale decision. Explicitly STOP instead
                # and let the next successful call re-decide from a standstill.
                logger.exception("Ollama call failed — sending STOP")
                _send(robot_sock, "AI_CMD:STOP")
                time.sleep(args.loop_rate)
                continue

            action = _parse_action(raw)
            if action is None:
                logger.warning(f"Unparseable LLM response — sending STOP, ignoring: {raw!r}")
                _send(robot_sock, "AI_CMD:STOP")
                time.sleep(args.loop_rate)
                continue

            action = _apply_safety(action, snap)

            if _send(robot_sock, f"AI_CMD:{action}"):
                logger.info(f"dist={snap.get('dist_cm')} ir={snap.get('ir')} -> {action}")
                history.append((snap, action))
            else:
                logger.warning("Send failed — robot connection lost")

            time.sleep(args.loop_rate)

    finally:
        _shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
