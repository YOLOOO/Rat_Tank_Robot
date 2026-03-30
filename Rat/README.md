# RAT BRAIN - Freenove Tank FNK0077 Control System

MVP implementation of a modular robot control system for the Freenove Tank (FNK0077) running on Raspberry Pi 5.

**Full Setup Guide**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)

## Quick Start

### On Robot (Raspberry Pi 5)

```bash
cd Rat/
chmod +x start_rat.sh stop_rat.sh
./start_rat.sh
```

This starts the brain server. You should see:
- TCP server listening on `0.0.0.0:5577`
- LEDs flashing green (IDLE state)

### On DEV PC

```bash
cd Rat/
python3 controller_sender_client.py --host <ROBOT_IP>
```

Controls:
- **A** - LEFT (previous item)
- **D** - RIGHT (next item)
- **S** - SELECT (run behavior)
- **Q** - QUIT

## System Architecture

```
[MNT Mouse Ball / Keyboard on DEV PC]
           ↓
   controller_sender_client.py
           ↓ (TCP: commands)
  control_receiver_server.py (Robot Pi)
           ↓
    brain_state.py (State Machine)
           ↓
    behaviors / missions
           ↓
   common_hardware/
```

### States

- **IDLE**: Selection menu, LEDs flash with selection color
- **RUNNING_BEHAVIOR**: Executing selected behavior
- **RUNNING_MISSION**: Executing selected mission
- **ERROR**: Red LED flash, waiting for restart

## Project Structure

```
Rat/
├── config.py                    # Central configuration
├── controller_sender_client.py  # DEV PC client (keyboard input)
├── start_rat.sh                 # Start script
├── stop_rat.sh                  # Stop script
│
├── rat_brain/                   # Core state machine
│   ├── __init__.py
│   ├── brain_state.py           # Main state machine
│   └── control_receiver_server.py  # TCP server
│
├── behavior_scripts/            # Modular behaviors
│   ├── __init__.py
│   ├── base_behavior.py         # Base class
│   ├── dance_demo.py            # DANCE behavior
│   ├── patrol.py                # PATROL behavior
│   └── toy_car_picker.py        # SCAN behavior
│
├── missions/                    # Larger routines
│   ├── __init__.py
│   ├── robot_wars.py            # WARS mission
│   └── obstacle_course.py       # OBSTACLE mission
│
├── common_hardware/             # GPIO Abstraction Layer
│   ├── __init__.py
│   ├── leds.py                  # LED control
│   ├── motors.py                # Motor control
│   ├── distance.py              # Distance sensor
│   └── tracking.py              # Tracking sensor
│
└── lib_utils/                   # Utility libraries
    └── __init__.py
```

## Configuration

Edit `config.py` to:
- Change server host/port
- Register new behaviors
- Set LED colors and timings
- Configure motor pins
- Adjust motor speeds

## Local Dependencies

**All dependencies are vendored locally** in `lib_utils/`:

- **rpi_ws281x** - LED control library
- **pi-hardware-pwm** - Raspberry Pi 5 PWM overlay setup scripts

No external package downloads needed! See [lib_utils/README.md](lib_utils/README.md) for details.

### PWM Setup (One-time on Pi 5)

```bash
cd Rat/lib_utils/pi-hardware-pwm/
sudo ./setup_pwm_overlay.sh
sudo reboot
```

This enables PWM on GPIO pins for motor control.

## Adding New Behaviors

### 1. Create a new file in `behavior_scripts/`

```python
from behavior_scripts.base_behavior import BaseBehavior

class Behavior(BaseBehavior):
    name = "EXAMPLE"
    color = (100, 100, 100)  # RGB
    
    def run(self, brain) -> bool:
        # Access motors, LEDs, sensors via brain
        brain.motor_controller.forward(100)
        brain.led_controller.set_color(self.color)
        
        # Return False to exit behavior
        return True
```

### 2. Register in `config.py`

```python
BEHAVIORS = {
    "EXAMPLE": ("behavior_scripts.example_behavior", (100, 100, 100), 4),
}
```

That's it! The behavior automatically appears in the selection menu.

## Brain API

Available in behaviors/missions via `brain` parameter:

```python
# Motors
brain.motor_controller.forward(speed)      # 0-255
brain.motor_controller.backward(speed)
brain.motor_controller.spin_left(speed)
brain.motor_controller.spin_right(speed)
brain.motor_controller.stop()

# LEDs
brain.led_controller.set_color((R, G, B))
brain.led_controller.turn_off()
brain.led_controller.flash((R, G, B), interval=0.5)
brain.led_controller.pulse((R, G, B), cycles=3)

# Sensors
brain.distance_sensor.read_distance()       # cm
brain.tracking_sensor.read_value()          # 0-255
brain.tracking_sensor.is_tracking_line()    # bool
```

## Commands

TCP protocol (newline-delimited):
```
LEFT\n
RIGHT\n
SELECT\n
STOP\n
```

Example: `nc robot_ip 5577` then type `LEFT\n`

## Hardware Abstraction

**No GPIO access outside `common_hardware/`**

All hardware calls go through the abstraction layer in `common_hardware/`, enabling:
- Easy simulation mode (no RPi GPIO)
- Hardware swapping
- Testing without hardware

## Execution Flow

1. Robot boots → `start_rat.sh`
2. Brain starts in IDLE state
3. LEDs flash with selected item color
4. PC sends: `LEFT`, `RIGHT`, `SELECT`
5. Brain processes command:
   - LEFT/RIGHT: cycle menu
   - SELECT: launch behavior
6. Behavior executes
7. Returns to IDLE
8. Repeat

## Safety

- Motors stop on error
- Motors stop on disconnect
- Motors stop on script end
- No runaway behavior
- Error state (red LED flash) on crash

## Testing Without Hardware

The system runs in **simulation mode** if GPIO libraries aren't available:
- Motors: logged but not executed
- LEDs: logged but not executed
- Sensors: return dummy values

Perfect for PC-based testing!

## Future Phases

Designed to support:
- [ ] Real MNT mouse ball input
- [ ] Emergency stop button
- [ ] Non-blocking behavior execution
- [ ] Behavior cancellation
- [ ] Mission chaining
- [ ] Sensor integration
- [ ] Return-to-home
- [ ] Bidirectional communication
- [ ] Script auto-discovery

## Troubleshooting

### Can't connect robot and PC
- Check IP address: `hostname -I` on robot
- Check firewall: port 5577 must be open
- Test with: `nc <robot_ip> 5577`

### LEDs not working
- Running in simulation mode? Check GPIO library installed
- Check pin configuration in `config.py`

### Motors not responding
- Check motor pins in `config.py`
- Check PWM frequency setting
- Running in simulation mode? Check logs

### Brain crashes
- Check Python syntax: `python3 -m py_compile rat_brain/brain_state.py`
- Check imports: verify all modules exist
- Run with `./start_rat.sh` to see error output

## References

- Freenove Tank: https://freenove.com/
- Raspberry Pi documentation
- Python GPIO: RPi.GPIO, Adafruit libraries

---

**Built with modularity, simplicity, and expansion in mind.**
