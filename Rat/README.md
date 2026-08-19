# RAT BRAIN - Freenove Tank FNK0077 Control System

MVP implementation of a modular robot control system for the Freenove Tank (FNK0077) running on Raspberry Pi 5.

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
│   ├── camera_test.py           # CAMERA_TEST
│   ├── motion_indication_test.py  # MOTION_TEST
│   ├── obstacle_course.py       # OBSTACLE_COURSE
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
```

Example: `nc robot_ip 5577` then type `LEFT` + Enter.

## Behavior Scripts

`behavior_scripts/` contains reusable building blocks for missions — not registered items themselves.

- **motor/forward.py**, **backward.py**, **stop.py**, **curve_turn.py**, **turn_degree.py** — convenience wrappers around `common_hardware.motor` that also check halt state
- **utilities/check_halt.py** — `is_halted(brain)` helper used by all motor behaviors

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
- [ ] Bidirectional communication (sensor data back to PC)
- [ ] Script auto-discovery

## References

- Freenove Tank: https://freenove.com/
- Raspberry Pi documentation
- Python GPIO: gpiozero with lgpio backend

---

**Built with modularity, simplicity, and expansion in mind.**
