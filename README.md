# Rat Tank Robot

Freenove FNK0077 tank robot running a custom brain on Raspberry Pi 5 with PCB v2.

---

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

---

## Repository layout

```
Rat/
├── config.py                   # Single source of truth for all settings
├── start_rat.sh                # Start the brain (detached, logs to rat_brain.log)
├── stop_rat.sh                 # Stop the brain cleanly (motors off, LEDs off)
├── rat_brain/
│   ├── brain_state.py          # Core state machine (IDLE → RUNNING_MISSION → ERROR)
│   └── control_receiver_server.py  # TCP command receiver
├── common_hardware/
│   ├── motor.py                # Motor driver (lgpio backend)
│   ├── spi_ledpixel.py         # SPI LED driver
│   ├── servo.py                # Servo driver (hardware PWM)
│   ├── infrared.py             # IR line sensors
│   └── ultrasonic.py           # Ultrasonic distance sensor
├── missions/                   # Selectable missions (registered in config.MISSIONS)
│   ├── test.py                 # Hardware test mission
│   └── remote_control.py       # Trackball remote control mission
├── behavior_scripts/           # Reusable motion building blocks used by missions
└── controller_sender_client.py # Run on dev PC to send commands over TCP
```

---

## On the robot — starting and stopping

### Start

```bash
cd ~/Rat_Tank_Robot/Rat
./start_rat.sh
```

The brain starts detached. The terminal returns immediately.

### Watch output

```bash
tail -f rat_brain.log
```

Ctrl+C stops tailing — the brain keeps running.

### Stop

```bash
./stop_rat.sh
```

This sends SIGINT to the brain process so the cleanup handler runs:
motors are stopped, LEDs are turned off, sockets are closed.

---

## On the dev PC — connecting the controller

```bash
python3 controller_sender_client.py
```

Default robot IP is set in `config.py` (`ROBOT_IP`). The controller connects over TCP on port 5577.

### MNT Trackball controls

| Input | Action |
|-------|--------|
| Ball left/right | Steer |
| Ball forward/back | Drive |
| Button (mapped) | HALT / SELECT |

---

## Configuration

All settings live in `config.py` — GPIO pins, speeds, IP addresses, mission registry, LED colours, servo limits. No other file should hardcode hardware values.

### Adding a mission

1. Create `missions/my_mission.py` with a `run(brain)` function that returns `False` when done.
2. Register it in `config.MISSIONS`:

```python
MISSIONS = {
    "MY_MISSION": ("missions.my_mission", (255, 0, 255), 3),
}
```

The brain picks it up automatically on next start.

---

## Servo calibration

An interactive terminal tool for finding safe angle limits per servo channel. Run it on the robot with the brain stopped.

```bash
cd ~/Rat_Tank_Robot/Rat
python3 tools/servo_calibrate.py --channel 0
python3 tools/servo_calibrate.py --channel 1
```

| Key | Action |
|-----|--------|
| `k` / UP | +1° |
| `j` / DOWN | -1° |
| `K` | +10° |
| `J` | -10° |
| `m` | mark current angle as MIN |
| `x` | mark current angle as MAX |
| `p` | print the marked limits (ready to paste into config.py) |
| `q` | quit |

When done, copy the printed `SERVO_CH0_MIN` / `SERVO_CH0_MAX` values into `config.py`.

---

## Dependencies (robot side)

```bash
pip install gpiozero lgpio pigpio spidev numpy rpi-hardware-pwm
sudo pigpiod -l -s 1   # start pigpiod daemon (start_rat.sh does this automatically)
```
