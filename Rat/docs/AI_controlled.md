# Feature: AI_controlled Mission

Local-LLM-driven autonomous control. The robot enters a waiting state and is driven entirely by a language model running on the dev PC. The model receives live sensor data (distance, IR, camera snapshots) and decides what action to take each control cycle.

---

## Architecture Overview

```
[Dev PC]
  AI_controller_client.py
  ├── Ollama API (localhost:11434)     ← LLM reasoning
  ├── TCP client → robot:5577         ← sends AI_CMD: commands
  └── TCP server  0.0.0.0:5578        ← receives telemetry from robot

[Robot Pi]
  missions/AI_controlled.py
  ├── Telemetry thread → devpc:5578   ← pushes JSON sensor data
  ├── Command queue  ← 5577           ← receives AI_CMD: commands
  └── Sensor reads (ultrasonic, IR, camera)
```

Two TCP channels replace the previous one-way flow. The existing command channel (port 5577) is unchanged and untouched — the new telemetry channel (port 5578) runs in the opposite direction over a second connection opened by the robot.

---

## New Files

| File | Side | Purpose |
|------|------|---------|
| `missions/AI_controlled.py` | Robot | Mission module; tick-based, polls sensors, dispatches `AI_CMD:*` |
| `AI_controller_client.py` | Dev PC | LLM loop; receives telemetry, calls Ollama, sends commands |

---

## Config Additions (`config.py`)

Add these to the end of `config.py` (both sides import it, but `AI_controller_client.py` only needs the subset that applies to the dev PC):

```python
# ============================================================================
# AI CONTROLLER CONFIGURATION
# ============================================================================
AI_TELEMETRY_PORT       = 5578          # Robot → Dev PC telemetry channel
AI_TELEMETRY_RATE       = 0.2           # Seconds between telemetry sends (5 Hz)
AI_CAMERA_RATE          = 2.0           # Seconds between camera snapshots (0 = disabled)
AI_CAMERA_SIZE          = (320, 240)    # Snapshot resolution for LLM consumption
AI_CAMERA_JPEG_QUALITY  = 70            # JPEG quality for snapshots (lower = smaller payload)

AI_OLLAMA_HOST          = "http://localhost:11434"
AI_DEFAULT_MODEL        = "llava"       # Any Ollama model; vision models receive images
AI_LOOP_RATE            = 1.0           # Seconds between LLM calls (1 Hz default)
AI_COMMAND_HISTORY      = 5            # How many past actions to include in LLM context
```

Register the mission in `MISSIONS`:

```python
"AI_CONTROLLED": ("missions.AI_controlled", (0, 100, 255), 5),  # Cyan-blue
```

---

## Telemetry Format (Robot → Dev PC)

Newline-delimited JSON sent over port 5578 at `AI_TELEMETRY_RATE` Hz.

```json
{
  "t":        1234567890.123,
  "dist_cm":  42.5,
  "ir":       [0, 1, 0],
  "motor_l":  2048,
  "motor_r":  2048,
  "arm":      "up",
  "grip":     "open",
  "frame_b64": "<base64-encoded JPEG string>"
}
```

- `dist_cm`: ultrasonic reading in cm. `-1` means timeout/error.
- `ir[0,1,2]`: left/center/right IR line sensors, `1` = line detected.
- `motor_l / motor_r`: current commanded duty (-4095 to +4095).
- `arm`: `"up"` or `"down"` (tracks last toggle state).
- `grip`: `"open"` or `"closed"`.
- `frame_b64`: present only when a fresh camera snapshot is available; absent otherwise. Base64-encodes a JPEG at `AI_CAMERA_SIZE` resolution.

The dev PC client always uses the most recently received telemetry when it builds the LLM prompt. If `frame_b64` is absent (no camera snapshot yet, or camera disabled), the LLM prompt is text-only.

---

## AI Command Set (`AI_CMD:*`)

The `AI_controlled` mission understands this command vocabulary. All commands are prefixed `AI_CMD:` to avoid clashing with other missions' command handlers.

| Command | Effect |
|---------|--------|
| `AI_CMD:FORWARD` | `motor.forward(MOTOR_SPEED_NORMAL)` |
| `AI_CMD:FORWARD:slow` | `motor.forward(MOTOR_SPEED_SLOW)` |
| `AI_CMD:FORWARD:fast` | `motor.forward(MOTOR_SPEED_FAST)` |
| `AI_CMD:BACKWARD` | `motor.backward(MOTOR_SPEED_NORMAL)` |
| `AI_CMD:BACKWARD:slow` | `motor.backward(MOTOR_SPEED_SLOW)` |
| `AI_CMD:BACKWARD:fast` | `motor.backward(MOTOR_SPEED_FAST)` |
| `AI_CMD:SPIN_LEFT` | `motor.spin_left(MOTOR_SPEED_NORMAL)` |
| `AI_CMD:SPIN_RIGHT` | `motor.spin_right(MOTOR_SPEED_NORMAL)` |
| `AI_CMD:CURVE:left:right` | `motor.curve(left, right)` — values -4095 to 4095 |
| `AI_CMD:STOP` | `motor.stop()` |
| `AI_CMD:ARM_UP` | servo CH0 → `SERVO_CH0_MAX` (70°) |
| `AI_CMD:ARM_DOWN` | servo CH0 → `SERVO_CH0_MIN` (150°) |
| `AI_CMD:GRIP_OPEN` | servo CH1 → `SERVO_CH1_MIN` (80°) |
| `AI_CMD:GRIP_CLOSE` | servo CH1 → `SERVO_CH1_MAX` (155°) |
| `AI_CMD:SNAPSHOT` | Force an immediate camera capture on the next sensor poll tick |

Commands are persistent: motors keep running at the last commanded speed until a new command arrives (same model as `remote_control`). The LLM must explicitly send `AI_CMD:STOP` to halt movement.

`HALT` still works as always — bypasses the queue, stops everything, returns to IDLE.

---

## Robot Mission Implementation Notes (`missions/AI_controlled.py`)

### Module-level state

```python
_initialized       = False
_telemetry_thread  = None
_telemetry_sock    = None   # socket to dev PC port 5578
_camera            = None
_last_camera_time  = 0.0
_force_snapshot    = False
_arm_up            = False
_grip_closed       = False
_motor_l           = 0
_motor_r           = 0
```

### Tick flow (`run(brain) -> bool`)

```
1. if is_halted(brain) → motor.stop(), teardown telemetry, return False
2. On first tick (_initialized=False):
   a. motor.stop()
   b. Set LED cyan-blue
   c. Open Camera instance (AI_CAMERA_SIZE)
   d. Start _telemetry_thread (daemon) → connects to dev PC:AI_TELEMETRY_PORT
   e. _initialized = True
3. Read sensors:
   a. ultrasonic.get_distance()
   b. infrared.read_all_infrared() → split into [ir0, ir1, ir2]
   c. If (time.time() - _last_camera_time) >= AI_CAMERA_RATE or _force_snapshot:
      - camera.get_frame() or subprocess rpicam-still → JPEG bytes
      - _last_snapshot_b64 = base64.b64encode(jpeg_bytes).decode()
      - _last_camera_time = time.time()
      - _force_snapshot = False
4. Drain command queue (non-blocking):
   a. For each AI_CMD: line → dispatch to motor/servo
   b. AI_CMD:SNAPSHOT → set _force_snapshot = True
5. return True
```

### Telemetry thread

Runs as a daemon thread. Loop:
1. Connect to dev PC (retry on failure, 2s back-off)
2. Every `AI_TELEMETRY_RATE` seconds: build JSON from current module-level state, send as `json.dumps(...) + "\n"`
3. On disconnect: reconnect loop
4. Exits when `_initialized` is False (mission ended)

The thread reads sensor values via module-level variables (no locking needed — Python GIL makes simple float/list reads safe enough here).

### Teardown

When `run()` returns False (HALT or error):
1. Set `_initialized = False` (signals telemetry thread to exit)
2. Close telemetry socket
3. Close camera
4. `motor.stop()`
5. Reset all module-level state to defaults for clean re-entry

---

## Dev PC Client Implementation Notes (`AI_controller_client.py`)

### Startup

```
python AI_controller_client.py --host <ROBOT_IP> --task "navigate to the wall and stop 20cm from it"
```

Optional flags:
- `--model llava` (default from config)
- `--camera-rate` to override how often images are sent to the LLM (independent of how often they arrive)
- `--loop-rate 1.0`

### Main loop

```
1. Start TCP server on 0.0.0.0:AI_TELEMETRY_PORT (background thread, stores latest telemetry)
2. Connect robot_connection to ROBOT_IP:SERVER_PORT
3. Send SELECT via robot_connection to launch AI_CONTROLLED mission on robot
4. Every AI_LOOP_RATE seconds:
   a. Read latest telemetry snapshot (dist_cm, ir, arm, grip, frame_b64)
   b. Build LLM prompt (see below)
   c. POST to Ollama API
   d. Parse response → one AI_CMD: line
   e. Send command to robot
   f. Append (sensor_snapshot, command) to history ring buffer (AI_COMMAND_HISTORY)
5. Ctrl-C → send HALT to robot
```

### Ollama API call

```python
import requests, base64

payload = {
    "model": model_name,
    "prompt": built_prompt,
    "stream": False,
}
if frame_b64 and model_supports_vision:
    payload["images"] = [frame_b64]

response = requests.post(f"{AI_OLLAMA_HOST}/api/generate", json=payload, timeout=10)
action = response.json()["response"].strip().upper()
```

Vision capability detection: call `GET /api/show` with the model name and check if `"vision"` is in `details.families` or the model name contains `llava`, `moondream`, `llava-phi`, `bakllava`.

### LLM System Prompt Template

```
You are the brain of a small tracked robot (tank-style, two independent tracks).
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

Respond with one action:
```

`{image_line}` is `"  camera  : [image attached]"` when a JPEG frame is included, or omitted when text-only.

`{history}` is the last `AI_COMMAND_HISTORY` entries formatted as:
```
  [state: dist=42.5 ir=[0,1,0]] → FORWARD
  [state: dist=35.0 ir=[0,0,0]] → FORWARD
```

---

## Recommended Ollama Models

| Model | Size | Vision | Speed | Notes |
|-------|------|--------|-------|-------|
| `moondream` | 1.7B | Yes | Very fast | Best choice for real-time vision loop |
| `llava-phi3` | 3.8B | Yes | Fast | Good quality, still manageable |
| `llava:7b` | 7B | Yes | Moderate | Better reasoning, slower loop |
| `llama3.2:3b` | 3B | No | Very fast | Text-only, good at following strict format |
| `phi3.5` | 3.8B | No | Fast | Text-only, strong instruction following |

For real-time control (1 Hz loop), start with `moondream` (vision) or `llama3.2:3b` (text-only). Use `llava:7b` only if you slow the loop to 2–3 seconds.

---

## Dev PC Setup Guide

### Prerequisites

- Windows 10/11 or Linux
- Python 3.10+
- Git repo already cloned
- Robot running and reachable on the network

---

### Step 1 — Install Ollama

**Windows:**
1. Go to https://ollama.com/download and download the Windows installer
2. Run the installer — it installs Ollama and starts it as a background service automatically
3. Verify: open a terminal and run:
   ```powershell
   ollama --version
   ```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

### Step 2 — Pull a model

Choose one based on your hardware and whether you want vision:

```powershell
# Fast vision model (recommended starting point):
ollama pull moondream

# Larger vision model (better reasoning, needs ~6GB VRAM or RAM):
ollama pull llava

# Text-only, very fast (no camera):
ollama pull llama3.2:3b
```

The first pull downloads the model weights (~1–7 GB depending on model). Subsequent runs are instant.

---

### Step 3 — Verify Ollama is running

Ollama should already be running as a service after installation. Test it:

```powershell
curl http://localhost:11434/api/tags
```

You should see a JSON response listing installed models. If you get a connection error:

```powershell
# Start manually:
ollama serve
```

Leave that terminal open, or configure it as a Windows service (the installer does this automatically on Windows).

---

### Step 4 — Install Python dependencies (dev PC side)

From the `Rat/` directory:

```powershell
pip install requests pillow
```

- `requests` — Ollama REST API calls
- `pillow` — optional, for resizing snapshots client-side if needed

The existing `requirements.txt` is robot-only (GPIO libs). Do not install it on the dev PC.

---

### Step 5 — Configure the robot IP

In `config.py`, confirm `ROBOT_IP` matches your robot:

```python
ROBOT_IP = "192.168.0.237"   # ← change to your robot's IP
```

Find the robot's IP on the Pi:
```bash
hostname -I
```

Also confirm the new AI config block is added (see Config Additions section above).

---

### Step 6 — Start the robot

On the robot Pi:
```bash
cd Rat/
./start_rat.sh
```

The brain will now include `AI_CONTROLLED` in the mission menu.

---

### Step 7 — Run the AI controller client

On the dev PC, from `Rat/`:

```powershell
python AI_controller_client.py --host 192.168.0.237 --task "navigate toward the nearest wall and stop 20cm away from it"
```

The client will:
1. Connect to the robot
2. Select the `AI_CONTROLLED` mission automatically
3. Start receiving telemetry
4. Begin the LLM control loop

To stop: press `Ctrl-C`. This sends `HALT` to the robot before exiting.

---

### Step 8 — Optional: test the LLM locally first

Before connecting to the robot, you can verify the model responds correctly:

```powershell
ollama run llama3.2:3b "You control a robot. dist_cm=45, ir=[0,0,0]. Task: approach the wall slowly. Respond with one action only."
```

Expected response: `FORWARD:SLOW` (or similar single-word action).

---

## Firewall Notes

| Port | Direction | Purpose |
|------|-----------|---------|
| 5577 | Dev PC → Robot | Existing command channel |
| 5578 | Robot → Dev PC | New telemetry channel |
| 11434 | localhost | Ollama API (local only) |

On Windows, the first time `AI_controller_client.py` opens port 5578, the Windows Firewall will prompt — allow it for private networks.

On the robot, port 5578 is outbound (robot connects to dev PC), so no firewall change needed on the Pi.

---

## Implementation Checklist

- [ ] Add AI config block to `config.py`
- [ ] Register `AI_CONTROLLED` mission in `MISSIONS`
- [ ] Implement `missions/AI_controlled.py` (tick loop, telemetry thread, sensor reads, command dispatch)
- [ ] Implement `AI_controller_client.py` (telemetry server thread, Ollama client, command sender, LLM loop)
- [ ] Test text-only path with `llama3.2:3b` and ultrasonic only
- [ ] Test vision path with `moondream` and camera snapshots
- [ ] Verify `HALT` still works immediately mid-LLM-call
- [ ] Add `AI_CONTROLLED` entry to README.md mission table
