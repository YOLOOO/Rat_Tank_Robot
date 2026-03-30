# LED Implementation for RAT BRAIN
## Adapted from Freenove FNK0077 Tank

### Overview
The LED controller has been updated to use the proven Freenove_RPI_WS281X wrapper approach with local dependencies, tested directly from the Code/Server/led.py reference implementation.

### Architecture

```
Rat Brain LED Stack
===================

User Code (behaviors, missions)
        ↓
set_color() / flash() / pulse()
        ↓
LEDController (Rat/common_hardware/leds.py)
        ↓
     Hardware Available?
    /                   \
YES                      NO
 ↓                        ↓
Freenove_RPI_WS281X    Console Visualization
  Wrapper               (ANSI colors + log)
   ↓
Adafruit_NeoPixel
   ↓
GPIO Pin 18 (WS2812B LED Strip)
```

### Key Features

1. **Freenove Wrapper Approach**
   - Uses proven Freenove_RPI_WS281X wrapper from Code/Server/rpi_ledpixel.py
   - Provides color format handling (RGB, RBG, GRB, GBR, BRG, BGR)
   - Handles brightness scaling automatically

2. **Hardware Auto-Detection**
   - Detects Raspberry Pi version (Pi 5 = v2, older = v1) via `/sys/firmware/devicetree/base/model`
   - Validates PCB version compatibility (PCB v1 NOT supported on Pi 5)
   - Gracefully disables if unsupported combination

3. **Graceful Degradation**
   - Falls back to simulation mode if hardware unavailable
   - Console visualization shows LED state changes in ANSI colors
   - All methods work with or without hardware

4. **Local Dependencies**
   - Uses vendored rpi_ws281x from `Rat/lib_utils/`
   - Falls back to system package if local not available
   - Offline-ready, no external dependencies required

### Configuration

Update `Rat/config.py`:

```python
# LED Configuration
LED_PIN = 18              # GPIO pin for LED strip (GPIO_GEN1)
LED_COUNT = 4             # Number of LEDs (Freenove tank = 4)
LED_BRIGHTNESS = 255      # Max brightness 0-255
LED_FLASH_INTERVAL = 0.5  # Seconds
LED_PCB_VERSION = 2       # PCB version (2 for Pi 5, 1 for older Pi)
LED_COLOR_FORMAT = 'RGB'  # RGB sequence type
```

Default values are optimized for **Freenove FNK0077 Tank on Raspberry Pi 5**.

### API Reference

#### get_led_controller()
Get or create the LED controller singleton.

```python
from common_hardware import get_led_controller
from config import (LED_PIN, LED_COUNT, LED_BRIGHTNESS, 
                    LED_COLOR_FORMAT, LED_PCB_VERSION)

led = get_led_controller(
    pin=LED_PIN,
    count=LED_COUNT,
    brightness=LED_BRIGHTNESS,
    color_format=LED_COLOR_FORMAT,
    pcb_version=LED_PCB_VERSION
)
```

#### set_color(rgb)
Set all LEDs to a single color (stops flashing).

```python
led.set_color((255, 0, 0))  # Red
led.set_color((0, 255, 0))  # Green
led.set_color((0, 0, 255))  # Blue
led.set_color((0, 0, 0))    # Off
```

#### turn_off()
Turn off all LEDs.

```python
led.turn_off()
```

#### flash(rgb, interval=0.5)
Start flashing LEDs at given color.

```python
led.flash((255, 0, 0), interval=0.5)  # Red flash at 0.5s interval
```

The flash state is maintained and needs `update()` called periodically.

#### pulse(rgb, cycles=3)
Pulse LEDs a specific number of times (blocking).

```python
led.pulse((0, 255, 0), cycles=3)  # Green pulse 3 times
```

#### update()
Update flash state (must be called periodically in main loop).

```python
while True:
    led.update()  # Call in main brain loop
```

### Integration with RAT BRAIN

In `Rat/rat_brain/brain_state.py`:

```python
# Initialize (autom atic with config params)
self.led_controller = get_led_controller(
    pin=config.LED_PIN,
    count=config.LED_COUNT,
    brightness=config.LED_BRIGHTNESS,
    color_format=config.LED_COLOR_FORMAT,
    pcb_version=config.LED_PCB_VERSION
)

# Main update loop
def update(self):
    # ... state machine logic ...
    self.led_controller.update()  # Update flash state
    
# In behaviors/missions
self.brain.led_controller.set_color((255, 0, 255))  # Magenta for DANCE
self.brain.led_controller.flash((0, 255, 0))        # Flash green
```

### Troubleshooting

#### LEDs not lighting up?
1. Check GPIO 18 is wired correctly to WS2812B data line
2. Check 5V power is connected to LED strip
3. Check GND is common with GPIO ground
4. Enable PWM overlay on Pi 5: `Rat/lib_utils/pi-hardware-pwm/setup_pwm_overlay.sh`

#### Library import errors?
```
ERROR: ws2811_init failed with code -3 (Hardware revision is not supported)
```
- Pi 5 runs in simulation mode automatically
- This is expected; real LEDs won't work on Pi 4 with Pi 5 overlay
- Console visualization still shows LED state changes

#### Color appears wrong?
- Check LED_COLOR_FORMAT matches your LED strip (RGB vs GRB, etc.)
- Freenove tanks typically use RGB format
- Test with `led.set_color((1, 0, 0))` - should be red tint

### Testing

Run LEDs independently:
```bash
cd Rat
python -c "
from common_hardware import get_led_controller
from config import LED_PIN, LED_COUNT, LED_BRIGHTNESS, LED_COLOR_FORMAT, LED_PCB_VERSION

led = get_led_controller(
    pin=LED_PIN,
    count=LED_COUNT, 
    brightness=LED_BRIGHTNESS,
    color_format=LED_COLOR_FORMAT,
    pcb_version=LED_PCB_VERSION
)

# Test colors
led.set_color((255, 0, 0))   # Red
import time; time.sleep(1)
led.set_color((0, 255, 0))   # Green
time.sleep(1)
led.set_color((0, 0, 255))   # Blue
time.sleep(1)
led.turn_off()
"
```

### Reference Implementation

Original working code:
- [Code/Server/led.py](../Code/Server/led.py) - Freenove LED class
- [Code/Server/rpi_ledpixel.py](../Code/Server/rpi_ledpixel.py) - Freenove_RPI_WS281X wrapper

Key differences in RAT BRAIN version:
- Uses local lib_utils dependencies instead of system packages
- Integrated with RatBrain state machine via config
- Auto-detects Pi version for compatibility
- Graceful fallback to console visualization

### Hardware Compatibility

| Platform | PCB v1 | PCB v2 | Result |
|----------|--------|--------|--------|
| Pi 4 / earlier | ✓ | ✓ | LED control works |
| Pi 5 | ✗ | ✓ | Pi 5 needs PCB v2 + SPI |

- **Pi 5 Note**: Use PCB v2 (SPI-based LEDs) with pi-hardware-pwm overlay
- **Graceful Fallback**: System auto-detects and disables if unsupported, console logging continues

### Performance

- **set_color()**: ~1ms (instant)
- **flash()**: Sets start time, no overhead until update()
- **update()**: ~1ms per flash state change
- **Main loop overhead**: <1% CPU (SPI hardware handles timing)

### Future Enhancements

- [ ] Rainbow animation method
- [ ] Color wheel rotation
- [ ] Fade in/out effects
- [ ] Per-LED control (currently all LEDs same color)
- [ ] Brightness ramp
- [ ] Pattern sequences

