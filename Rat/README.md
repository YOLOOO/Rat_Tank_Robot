# RAT BRAIN - Freenove Tank FNK0077 Control System

MVP implementation of a modular robot control system for the Freenove Tank (FNK0077) running on Raspberry Pi 5.

## Hardware

| Component | Detail |
|-----------|--------|
| Platform | Freenove FNK0077 tank |
| SBC | Raspberry Pi 5 |
| PCB | v2.0 |
| LEDs | 4x WS2812 via SPI (GRB) |
| Motors | 2x track motors via gpiozero/lgpio |
| Servos | Hardware PWM via pigpiod |
| Controller | MNT Reform Trackball (RP2040) over USB/TCP |

## Quick Start

### On Robot (Raspberry Pi 5)

```bash
cd Rat/
chmod +x start_rat.sh stop_rat.sh
./start_rat.sh
```

This starts the brain server. You should see:
- TCP server listening on `0.0.0.0:5577`
- LEDs lit with the selected mission color

### On DEV PC (Windows)

```powershell
cd Rat/
python controller_sender_client.py --host <ROBOT_IP>
```

Keyboard-only client, no extra dependencies. It has two modes, both read from the same keys:

Menu mode (default):
- **A** - LEFT (previous mission)
- **D** - RIGHT (next mission)
- **S** - SELECT (run mission — selecting REMOTE_CONTROL switches to drive mode)
- **H** - HALT (stop everything immediately)
- **Q** - QUIT

Drive mode (after selecting REMOTE_CONTROL):
- **W / S** - forward / backward
- **A / D** - spin left / spin right
- **SPACE** - stop moving (stays in drive mode)
- **R** - ARM_TOGGLE (raise/lower)
- **G** - GRIP_TOGGLE (open/close)
- **H** - HALT (stops the robot and returns to menu mode)
- **Q** - QUIT

Held-key driving isn't possible with plain console input (key presses, not press/release events), so each tap sets the motors to a fixed speed until the next tap changes it — tap W to go, tap SPACE to stop.

### AI Controller (local-LLM driven, DEV PC)

Requires [Ollama](https://ollama.com) running locally with a model pulled (`ollama pull llava` for a vision model — the default, or `ollama pull llama3.2:3b` for text-only). See [AI Controller Reference](#ai-controller-reference) below for the full flag list, wire format, safety model, and goal system.

```bash
pip install requests
./start_ai                                                          # demo run, all defaults from config.py
./start_ai --task "navigate toward the nearest wall and stop 20cm away from it"
./start_ai --goal-distance-cm 20 --goal-tolerance-cm 3 --max-duration-s 120
```

`./start_ai` is a thin wrapper that execs `AI_controller_client.py` with your extra args — run the client directly if you'd rather not use it. Selects the `AI_CONTROLLED` mission on the robot, opens a second TCP channel (port 5578) for the robot to stream telemetry back, and drives the robot with one Ollama call per loop tick (`AI_LOOP_RATE` in `config.py`). Ctrl-C sends HALT before exiting; the robot can also end the mission itself (goal reached, stuck, timed out, or a dead sensor), in which case the client exits 0 or 1 accordingly.

## System Architecture

```
[Keyboard on DEV PC]
           ↓
   controller_sender_client.py
           ↓ (TCP: commands)
  control_receiver_server.py (Robot Pi)
           ↓
    brain_state.py (State Machine)
           ↓
       missions/
           ↓
   behavior_scripts/   common_hardware/
```

### States

- **IDLE**: Selection menu, LED shows selected mission color
- **RUNNING_MISSION**: Executing selected mission
- **ERROR**: Red LED, auto-recovers to IDLE after 5s

## Project Structure

```
Rat/
├── config.py                    # Central configuration
├── controller_sender_client.py  # DEV PC client (keyboard input)
├── AI_controller_client.py      # DEV PC client (local-LLM driven, see AI Controller Reference below)
├── start_ai                     # DEV PC launcher — AI_controller_client.py with config.py defaults
├── requirements.txt              # Robot (Raspberry Pi) dependencies
├── start_rat.sh                 # Start script
├── stop_rat.sh                  # Stop script
│
├── rat_brain/                   # Core state machine
│   ├── __init__.py
│   ├── brain_state.py           # Main state machine
│   └── control_receiver_server.py  # TCP server
│
├── missions/                    # Selectable routines (registered in config)
│   ├── AI_controlled.py         # AI_CONTROLLED
│   ├── camera_test.py           # CAMERA_TEST
│   ├── motion_indication_test.py  # MOTION_TEST
│   ├── remote_control.py        # REMOTE_CONTROL
│   └── sensory_test.py          # SENSORY_TEST
│
├── behavior_scripts/            # Low-level building blocks used by missions
│   ├── __init__.py
│   ├── motor/
│   │   ├── forward.py
│   │   ├── backward.py
│   │   ├── stop.py
│   │   ├── curve_turn.py
│   │   └── turn_degree.py
│   └── utilities/
│       └── check_halt.py
│
├── common_hardware/             # GPIO Abstraction Layer
│   ├── __init__.py              # LED + servo singletons
│   ├── motor.py                 # Motor control (module-level functions)
│   ├── spi_ledpixel.py          # LED control (SPI, PCB v2)
│   ├── servo.py                 # Servo control
│   ├── ultrasonic.py            # Distance sensor
│   ├── infrared.py              # Line tracking sensor
│   └── camera.py                # Camera
│
├── tools/                       # Dev utilities
│   └── servo_calibrate.py       # Interactive servo calibration
│
└── lib_utils/                   # Vendored libraries
    └── pi-hardware-pwm/         # Raspberry Pi 5 PWM overlay setup
```

## Configuration

Edit `config.py` to:
- Change server host/port
- Register new missions
- Set LED colors and timings
- Configure motor and servo pins
- Adjust motor speeds and turn calibration
- Adjust `KEYBOARD_DRIVE_SPEED` for the keyboard remote-drive controls

## Local Dependencies

**All dependencies are vendored locally** in `lib_utils/`:

- **pi-hardware-pwm** - Raspberry Pi 5 PWM overlay setup scripts

No external package downloads needed for hardware drivers. See `requirements.txt` for Python package dependencies.

### PWM Setup (One-time on Pi 5)

```bash
cd Rat/lib_utils/pi-hardware-pwm/
sudo ./setup_pwm_overlay.sh
sudo reboot
```

This enables PWM on GPIO pins for motor control.

## Adding New Missions

### 1. Create a new file in `missions/`

Missions are plain modules with a `run(brain)` function. Return `True` to keep running each tick, `False` to exit and return to IDLE.

```python
import common_hardware.motor as motor
from common_hardware import get_led_controller
from behavior_scripts.utilities.check_halt import is_halted

def run(brain) -> bool:
    if is_halted(brain):
        motor.stop()
        return False

    motor.forward()
    return True
```

### 2. Register in `config.py`

```python
MISSIONS = {
    "MY_MISSION": ("missions.my_mission", (100, 100, 100), 5),
    #                                      RGB color       display order
}
```

The mission automatically appears in the selection menu.

## Hardware API

Available in missions via `import common_hardware.motor as motor` etc.:

```python
# Motors (common_hardware/motor.py — module-level functions)
import common_hardware.motor as motor
motor.forward(speed)          # speed: 0–4095, default MOTOR_SPEED_NORMAL
motor.backward(speed)
motor.spin_left(speed)
motor.spin_right(speed)
motor.set_motors(left, right) # independent left/right duty: -4095 to +4095
motor.curve(left, right)
motor.stop()

# LEDs (singleton via common_hardware/__init__.py)
from common_hardware import get_led_controller
leds = get_led_controller()
leds.set_all_led_rgb([R, G, B])
leds.led_close()

# Servos (singleton via common_hardware/__init__.py)
from common_hardware import get_servo_controller
servo = get_servo_controller()
servo.setServoPwm('0', angle)   # ch0 = arm
servo.setServoPwm('1', angle)   # ch1 = grip
servo.setServoStop('0')
servo.setServoStop('1')
```

### Brain object passed to missions

```python
brain.state               # current RobotState enum value
brain.command_server      # CommandReceiverServer — call .get_command(timeout=0)
brain.command_server.halt_flag  # True if HALT is pending
```

## TCP Commands

Newline-delimited, case-insensitive:

```
LEFT\n              # scroll menu left
RIGHT\n             # scroll menu right
SELECT\n            # launch selected mission
HALT\n              # emergency stop — bypasses queue, handled immediately
MOTOR:left:right\n  # set motor duties directly (-4095..+4095), used by remote_control
SERVO:ch:delta\n    # nudge servo ch (0=arm, 1=grip) by delta degrees
ARM_TOGGLE\n        # toggle arm up/down preset
GRIP_TOGGLE\n       # toggle grip open/closed preset
AI_CMD:*\n          # AI_CONTROLLED mission commands — see AI Controller Reference below
```

Example: `nc robot_ip 5577` then type `LEFT` + Enter.

`AI_CONTROLLED` additionally opens a second, robot-initiated TCP connection to the currently-connected controller's IP on port `AI_TELEMETRY_PORT` (5578, see `config.py`) to stream sensor telemetry back — see AI Controller Reference below for the wire format.

## AI Controller Reference

Local-LLM-driven autonomy. Two processes: `missions/AI_controlled.py` runs on the robot as a normal mission; `AI_controller_client.py` (or `./start_ai`) runs on the dev PC, feeds an [Ollama](https://ollama.com) model one prompt per loop tick, and turns its response into one `AI_CMD:` action sent back to the robot.

### Usage

```bash
./start_ai                                                          # all defaults from config.py
python AI_controller_client.py --host <ROBOT_IP> --task "..." [flags]
```

| Flag | Default (`config.py`) | Meaning |
|------|------------------------|---------|
| `--host` | `ROBOT_IP` | Robot IP address |
| `--task` | `AI_DEFAULT_TASK` | Natural-language task given to the LLM |
| `--model` | `AI_DEFAULT_MODEL` (`llava`) | Ollama model name — vision models get the camera frame attached |
| `--loop-rate` | `AI_LOOP_RATE` | Seconds between LLM calls |
| `--goal-distance-cm` | `AI_GOAL_DISTANCE_CM` (none) | Mission ends `GOAL_REACHED` once `dist_cm` is within `--goal-tolerance-cm` of this |
| `--goal-ir` | `AI_GOAL_IR` (none) | Mission ends `GOAL_REACHED` once the IR bitmask (`left<<2 \| center<<1 \| right`, 0-7) reads exactly this |
| `--goal-tolerance-cm` | `AI_GOAL_TOLERANCE_CM` | Tolerance for `--goal-distance-cm` |
| `--max-duration-s` | `AI_MAX_DURATION_S` (0 = disabled) | Mission ends `TIMEOUT` after this many seconds |

If both `--goal-distance-cm` and `--goal-ir` are given, both must be satisfied simultaneously. With neither given, the mission just runs until HALT, `STUCK`, `TIMEOUT` (if set), or `SENSOR_FAULT` — the sensor/stuck protections are always on regardless of whether a goal is configured.

### Wire format

`AI_CMD:` commands (dev PC → robot, existing command channel, port `SERVER_PORT`):

```
AI_CMD:FORWARD[:SLOW|:FAST]
AI_CMD:BACKWARD[:SLOW|:FAST]
AI_CMD:SPIN_LEFT
AI_CMD:SPIN_RIGHT
AI_CMD:CURVE:left:right          # -4095..4095 per track, same convention as motor_l/motor_r below
AI_CMD:STOP
AI_CMD:ARM_UP / AI_CMD:ARM_DOWN
AI_CMD:GRIP_OPEN / AI_CMD:GRIP_CLOSE
AI_CMD:SNAPSHOT                  # force an out-of-cycle camera capture
AI_CMD:GOAL:dist_cm:ir:tolerance_cm:max_duration_s   # sent once by the client right after mission select;
                                                      # -1 on dist_cm/ir means "no goal on that axis"
```

Telemetry (robot → dev PC, robot-initiated, port `AI_TELEMETRY_PORT`, newline-delimited JSON, ~5Hz):

```json
{
  "t": 1234567890.1,
  "dist_cm": 34.2,
  "ir": [0, 1, 0],
  "motor_l": -2048, "motor_r": -2048,
  "arm": "down", "grip": "closed",
  "status": "RUNNING", "reason": "",
  "frame_b64": "..."
}
```

`status` is `"RUNNING"` on every regular tick. The mission can end itself and report why in one final payload before it stops: `GOAL_REACHED`, `STUCK` (kept re-trying a blocked forward move past `AI_STUCK_TIMEOUT_S`), `TIMEOUT` (past `--max-duration-s`), or `SENSOR_FAULT` (a sensor stayed dead past `AI_SENSOR_FAULT_TIMEOUT_S`, or failed outright at mission start, in which case the robot aborts into `ERROR` instead — see below). `AI_controller_client.py` watches this field and exits 0 on `GOAL_REACHED`, 1 on anything else. `frame_b64` is only present the tick after a new camera frame was captured (`AI_CAMERA_RATE`), not on every payload.

### Safety model

Two independent layers, deliberately redundant:

1. **Onboard interlock** (robot, `missions/AI_controlled.py`, every ~50ms tick) — blocks any command that would drive a track forward while `dist_cm` is below `AI_MIN_OBSTACLE_CM` or reading `-1` (sensor error, treated as "obstacle"). This is the one that actually matters: it reacts on the live sensor reading regardless of what the dev PC last sent, so it isn't at the mercy of the LLM loop's slower cadence.
2. **Client-side override** (dev PC, `AI_controller_client.py`) — rewrites a forward-type LLM decision to `STOP` before it's even sent, using the same `AI_MIN_OBSTACLE_CM` threshold from `config.py`. Local models are unreliable about obeying the numeric rule in the prompt; this catches it a decision earlier than the onboard check would.

Also: before either layer runs, the robot pre-flight-checks both sensors (`AI_PREFLIGHT_READS` back-to-back reads on each) before arming motors or opening telemetry — a sensor that fails outright aborts the mission into `ERROR` rather than silently starting up.

## Behavior Scripts

`behavior_scripts/` contains reusable building blocks for missions — not registered items themselves. Every mission that touches motors (`AI_controlled.py`, `remote_control.py`, `motion_indication_test.py`) now goes through these wrappers instead of calling `common_hardware.motor` directly.

- **motor/forward.py**, **backward.py**, **stop.py**, **curve_turn.py**, **spin_left.py**, **spin_right.py**, **set_motors.py** — convenience wrappers around `common_hardware.motor` that also check halt state before issuing a command. Each `run(...)` (`stop.run` included, for API symmetry) returns `True` if the command was actually issued and `False` if it was skipped because a halt was already in flight — callers that track commanded motor state (see `AI_controlled.py`'s `_motor_l`/`_motor_r`) key off that return value rather than assuming the call went through.
- **motor/turn_degree.py** — spins in place for a calculated duration to approximate a degree turn. Complete as a behavior, but deliberately **not wired into any mission**: it blocks for the full turn (up to a few seconds), which would stall a mission's per-tick loop and its HALT/command responsiveness along with it. Wiring it in needs its own thread or a non-blocking redesign — left as a follow-up.
- **servo/ramp.py** — non-blocking, time-interpolated servo move (`step(channel, start_angle, target_angle, start_time, duration, brain)` → `(current_angle, done)`, plus `duration_for(start_angle, target_angle, speed)` for the `SLOW`/`MID`/`FAST` tiers in `config.SERVO_MOVE_FULL_SWEEP_*_S`). Unlike `turn_degree.py`, this one *is* safe to call from a per-tick mission loop — it never sleeps, just computes how far along a move should be by now and commands that angle. Wired into `AI_controlled.py`'s `ARM_UP`/`ARM_DOWN`/`GRIP_OPEN`/`GRIP_CLOSE` (each now takes an optional `:SLOW`/`:MID`/`:FAST` modifier, mirroring `FORWARD`/`BACKWARD`'s `:SLOW`/`:FAST`) and the matching vocabulary in `AI_controller_client.py`. Not wired into `remote_control.py`'s `ARM_TOGGLE`/`GRIP_TOGGLE` (still an instant snap) or `motion_indication_test.py`'s self-test sweep (has its own, separate ramp) — deliberately left alone since neither was asked for and changing the keyboard-teleop feel wasn't requested.
- **utilities/check_halt.py** — `is_halted(brain)` helper used by all motor and servo behaviors. Reads `brain.command_server.halt_flag` (set immediately, on the receiver thread, the instant HALT arrives) rather than `brain.halt_flag` (only ever true for a transient instant inside the main loop's own halt handling, never observable from inside a running mission) — see `MOTOR_SENSORY_REWORK_2026-08-29` in git history if a motor or sensor issue turns up near here.

## Hardware Abstraction

**No GPIO access outside `common_hardware/`**

All hardware calls go through the abstraction layer in `common_hardware/`, enabling simulation mode when GPIO libraries aren't available (motors and LEDs are logged but not executed, sensors return dummy values).

## Execution Flow

1. Robot boots → `start_rat.sh`
2. Brain starts in IDLE state, menu printed to console
3. LED shows selected mission color
4. PC sends: `LEFT`, `RIGHT`, `SELECT`, `HALT`
5. Brain processes command:
   - LEFT/RIGHT: cycle menu
   - SELECT: reload and launch mission module
   - HALT: stop all motion immediately, return to IDLE
6. Mission `run(brain)` called every tick (50ms)
7. Mission returns `False` → back to IDLE
8. Repeat

## Safety

- HALT bypasses the command queue — handled before any queued command
- Motors stop on HALT, mission end, error, and disconnect
- ERROR state auto-recovers to IDLE after 5s
- `check_halt.is_halted(brain)` available in all behaviors for cooperative cancellation

## Troubleshooting

### Can't connect robot and PC
- Check IP address: `hostname -I` on robot
- Check firewall: port 5577 must be open
- Test with: `nc <robot_ip> 5577`

### LEDs not working
- Running in simulation mode? Check GPIO library installed
- Check `LED_PCB_VERSION` and `LED_COLOR_FORMAT` in `config.py`

### Motors not responding
- Check motor pins in `config.py`
- Check PWM frequency setting and that PWM overlay is installed
- Running in simulation mode? Check logs

### Brain crashes
- Check Python syntax: `python3 -m py_compile rat_brain/brain_state.py`
- Check imports: verify all modules exist
- Run with `./start_rat.sh` to see error output

## Future Phases

- [ ] Emergency stop button (pin reserved: GPIO26)
- [ ] Non-blocking mission execution (`camera_test.py` still blocks the brain tick)
- [ ] Mission chaining
- [ ] Return-to-home
- [x] Bidirectional communication (sensor data back to PC) — `AI_CONTROLLED` mission
- [ ] Script auto-discovery

## References

- Freenove Tank: https://freenove.com/
- Raspberry Pi documentation
- Python GPIO: gpiozero with lgpio backend

---

**Built with modularity, simplicity, and expansion in mind.**
