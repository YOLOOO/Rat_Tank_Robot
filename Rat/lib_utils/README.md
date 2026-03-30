# Local Dependencies

This folder contains vendored copies of external dependencies to avoid external package requirements.

## Contents

### `rpi_ws281x/` + `rpi_ws281x.py`
**Purpose**: LED strip control (WS2812/NeoPixel)  
**Usage**: 
```python
from lib_utils.rpi_ws281x import Adafruit_NeoPixel, Color
```

### `pi-hardware-pwm/`
**Purpose**: Raspberry Pi 5 PWM overlay setup

**Files**:
- `setup_pwm_overlay.sh` - Install PWM overlay on Pi 5
- `cleanup_pwm_overlay.sh` - Remove PWM overlay
- `pwm-pi5.dtbo` - Compiled device tree overlay
- `pwm-pi5-overlay.dts` - Device tree source

**Setup on Raspberry Pi 5**:
```bash
cd Rat/lib_utils/pi-hardware-pwm/
chmod +x setup_pwm_overlay.sh
sudo ./setup_pwm_overlay.sh
```

This enables PWM on GPIO pins for motor control.

## Why Local Copies?

1. **Consistency** - Exact version control
2. **Offline** - No external dependencies needed
3. **Control** - Modified versions if needed
4. **Raspberry Pi 5** - rpi_ws281x has compatibility issues, local fixes easier

## Updating Dependencies

To update from upstream:
```bash
# Navigate to Code/Libs/
cp -r Code/Libs/rpi-ws281x-python/library/rpi_ws281x Rat/lib_utils/
cp -r Code/Libs/pi-hardware-pwm/* Rat/lib_utils/pi-hardware-pwm/
```

## Import Notes

The system prefers local copies but falls back to system packages:
```python
try:
    from lib_utils.rpi_ws281x import Adafruit_NeoPixel
except ImportError:
    from rpi_ws281x import Adafruit_NeoPixel
```

This allows flexibility for development on different systems.
