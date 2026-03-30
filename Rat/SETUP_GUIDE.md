# RAT BRAIN - Setup & Dependency Guide

## Quick Setup

### 1. On Raspberry Pi 5

```bash
cd ~/Rat_Tank_Robot/Rat/

# Make scripts executable
chmod +x start_rat.sh stop_rat.sh
chmod +x lib_utils/pi-hardware-pwm/*.sh

# Optional: Setup PWM overlay (needed for motor PWM control)
cd lib_utils/pi-hardware-pwm/
sudo ./setup_pwm_overlay.sh
cd ../..

# Install Python dependencies (if not already installed)
pip3 install -r requirements.txt

# Start RAT BRAIN
./start_rat.sh
```

### 2. On DEV PC

```bash
cd Rat/
python3 controller_sender_client.py --host <ROBOT_IP>
```

---

## Dependencies (Vendored Locally)

All dependencies are included in `Rat/lib_utils/` - **no external package downloads needed**.

### `lib_utils/rpi_ws281x/`
**Purpose**: RGB LED strip control  
**Used by**: `common_hardware/leds.py`  
**Auto-loads**: Yes (via local import with fallback)

### `lib_utils/pi-hardware-pwm/`
**Purpose**: Raspberry Pi 5 PWM overlay setup  
**Components**:
- `setup_pwm_overlay.sh` - Enable PWM capability
- `cleanup_pwm_overlay.sh` - Disable PWM (if needed)
- `pwm-pi5.dtbo` - Compiled device tree overlay
- `pwm-pi5-overlay.dts` - Source file

**Why needed**: Raspberry Pi 5 changed boot process. PWM on GPIO needs device tree overlay modification.

---

## PWM Overlay Setup (One-Time on Pi 5)

The PWM overlay **must be set up once** for motor control to work:

```bash
cd Rat/lib_utils/pi-hardware-pwm/
sudo ./setup_pwm_overlay.sh
```

**What this does**:
1. Detects Pi version
2. For Pi 5: compiles `pwm-pi5-overlay.dts` → `pwm-pi5.dtbo`
3. Copies `.dtbo` file to `/boot/firmware/overlays/`
4. Adds `dtoverlay=pwm-pi5` to `/boot/firmware/config.txt`
5. **Requires reboot**: `sudo reboot`

**Verification** (after reboot):
```bash
# Should show PWM capability
cat /proc/device-tree/soc/pwm@*/status
# or
ls /sys/class/pwm/
```

---

## Requirements

Create `requirements.txt` has minimal dependencies:

```
RPi.GPIO>=0.7.0      # For motor control (on Pi)
adafruit-neopixel    # For LED control (has compatibility issues with Pi 5)
```

These are optional - system works in **simulation mode** without them.

---

## Library Import Strategy

The system uses a smart import fallback:

```python
try:
    from lib_utils.rpi_ws281x import Adafruit_NeoPixel, Color
except ImportError:
    from rpi_ws281x import Adafruit_NeoPixel, Color
```

**Priority**:
1. **Local copy** (`lib_utils/`) - For consistency and offline use
2. **System package** - If local not available
3. **Simulation mode** - If neither available (graceful degradation)

---

## Testing

### PC-Only Testing (No Hardware)
```bash
cd Rat/
python3 rat_brain/brain_state.py &
# In another terminal:
python3 controller_sender_client.py --host localhost
```

**Expected**: Everything works, all actions logged (no actual GPIO)

### Pi Testing (With Hardware)
```bash
./start_rat.sh
# Connect from PC
python3 controller_sender_client.py --host <PI_IP>
```

**Expected**: 
- LEDs flash (if connected)
- Motors respond (if connected)
- Commands work reliably

### Troubleshooting

| Issue | Solution |
|-------|----------|
| ImportError: `_rpi_ws281x` | Running on non-Pi platform (expected). Works on actual Pi. |
| Motors don't move | PWM overlay not installed. Run `setup_pwm_overlay.sh` and reboot. |
| LEDs don't light | Hardware issue or simulation mode. Check logs. |
| Connection refused | Check Pi IP, firewall port 5577. |

---

## Updating Dependencies

To refresh from upstream source:

```bash
# From repo root
cp -r Code/Libs/rpi-ws281x-python/library/rpi_ws281x Rat/lib_utils/
cp -r Code/Libs/pi-hardware-pwm/* Rat/lib_utils/pi-hardware-pwm/
git add Rat/lib_utils/
git commit -m "update: refresh vendored dependencies"
```

---

## Offline Usage

Because all dependencies are vendored locally, RAT BRAIN works:
✅ Without internet connection  
✅ Without `pip install`  
✅ With exact version control  
✅ With local modifications if needed

---

## Hardware Requirements (Physical Setup)

### For Motor Control
- 2x DC motors (left, right)
- Motor driver (L298N or similar)
- Pin config in `config.py`:
  - Left forward: GPIO 12
  - Left backward: GPIO 11
  - Right forward: GPIO 8
  - Right backward: GPIO 7

### For LED Control
- WS2812/NeoPixel LED strip (24 LEDs)
- Pin: GPIO 18 (configurable)
- Good power supply (5V recommended)

### Optional Sensors
- Ultrasonic distance sensor (GPIO 17)
- Line tracking sensor (GPIO 27)

---

## Next Steps

1. **Setup PWM** (one-time on Pi 5)
   ```bash
   cd Rat/lib_utils/pi-hardware-pwm/
   sudo ./setup_pwm_overlay.sh
   sudo reboot
   ```

2. **Connect Hardware** (motors, LEDs, sensors)

3. **Start Brain**
   ```bash
   ./start_rat.sh
   ```

4. **Connect Controller**
   ```bash
   python3 controller_sender_client.py --host <PI_IP>
   ```

5. **Test Commands**
   - Press `a` (LEFT)
   - Press `d` (RIGHT)
   - Press `s` (SELECT)
   - Watch robot respond!

---

## Support

- Check `common_hardware/` for GPIO abstraction details
- Look at `behavior_scripts/` for behavior examples
- See `config.py` for all settings
- Read `README.md` for architecture overview

**All code is simulation-compatible for PC testing!**
