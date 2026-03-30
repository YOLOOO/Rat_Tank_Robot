# Code/Server → Rat/ LED Adaptation Mapping

## Architecture Mapping

```
Code/Server (Reference Implementation)
┌─────────────────────────────────────┐
│ led.py                              │
│ - Led class                         │
│ - PCB/Pi version detection          │
│ - colorWipe(), Blink(), wheel()     │
│ - Graceful is_support_led_function  │
└────────┬────────────────────────────┘
         │
         ├─→ rpi_ledpixel.py
         │   Freenove_RPI_WS281X
         │   wrapper
         │
         ├─→ spi_ledpixel.py
         │   Freenove_SPI_LedPixel
         │   (for Pi 5 SPI LEDs)
         │
         └─→ parameter.py
             ParameterManager
             (Pi/PCB detection)

Rat/ (New Implementation)
┌──────────────────────────────────┐
│ Rat/common_hardware/leds.py      │
│ - LEDController class            │
│ - Pi/PCB detection (embedded)    │
│ - set_color(), flash(), pulse()  │
│ - Graceful fallback to sim mode  │
└────────┬──────────────────────────┘
         │
         ├─→ Rat/lib_utils/
         │   rpi_ws281x/
         │   (vendored dependency)
         │
         ├─→ Rat/config.py
         │   (config values)
         │
         └─→ Rat/rat_brain/brain_state.py
             (initialization)
```

## Class Mapping

| Code/Server | Rat/ | Purpose |
|-------------|------|---------|
| `Led.__init__()` | `LEDController.__init__()` | Initialize with version detection |
| `Led.colorWipe()` | `LEDController.set_color()` + no animation | Set solid color |
| `Led.Blink()` | `LEDController.set_color()` | Set color immediately |
| `Led.wheel()` | `LEDController._rgb_to_internal()` | Color format conversion |
| `Led.rainbow()` | Not implemented (future enhancement) | Rainbow animation |
| - | `LEDController.flash()` | Timed flashing (new) |
| - | `LEDController.pulse()` | Pulsing animation (new) |
| - | `LEDController.update()` | State update in loop (new) |
| `ParameterManager` | `_get_raspberry_pi_version()` | Pi detection function |
| - | `LEDController._is_hardware_supported()` | Compatibility check |
| - | `LEDController._init_hardware()` | Hardware initialization |
| - | `LEDController._rgb_to_internal()` | Color format mapping |

## Method Adaptation Details

### 1. Hardware Detection

**Code/Server (parameter.py)**:
```python
def get_raspberry_pi_version(self):
    result = subprocess.run(['cat', '/sys/firmware/devicetree/base/model'], 
                           capture_output=True, text=True)
    if "Raspberry Pi 5" in model:
        return 2  # Pi 5
    else:
        return 1  # older Pi
```

**Rat/ (leds.py)**:
```python
def _get_raspberry_pi_version() -> int:
    """Detect Raspberry Pi version."""
    # Same logic, wrapped in function
    # Pi 5 = version 2, older = version 1
    # Same detection via /sys/firmware/devicetree/base/model
```

### 2. Hardware Compatibility Check

**Code/Server (led.py)**:
```python
if pcb_version == 1 and pi_version == 2:
    print("PCB Version 1.0 is not supported on Raspberry PI 5.")
    is_support_led_function = False
```

**Rat/ (leds.py)**:
```python
if not self._is_hardware_supported():
    logger.warning(f"PCB v{pcb_version} not supported on Raspberry Pi {self.pi_version}")
    return  # Falls back to simulation mode
```

### 3. LED Initialization

**Code/Server (led.py)**:
```python
if pcb_version == 1 and pi_version == 1:
    self.strip = Freenove_RPI_WS281X(4, 255, 'RGB')
    is_support_led_function = True
elif pcb_version == 2:
    self.strip = Freenove_SPI_LedPixel(4, 255, 'GRB')
    is_support_led_function = True
```

**Rat/ (leds.py)**:
```python
# Use direct Adafruit_NeoPixel for Pi 4
# (Freenove wrapper adds unnecessary complexity)
self.strip = Adafruit_NeoPixel(
    count=4,
    pin=18,
    freq_hz=800000,
    dma=10,
    invert=False,
    brightness=255
)
if self.strip.begin():
    hardware_available = True
```

### 4. Color Setting

**Code/Server (led.py)**:
```python
def Blink(self, color, wait_ms=50):
    if self.is_support_led_function == False:
        return
    for i in range(self.strip.get_led_count()):
        self.strip.set_led_rgb_data(i, color)
        self.strip.show()
    time.sleep(wait_ms / 1000.0)
```

**Rat/ (leds.py)**:
```python
def set_color(self, rgb: Tuple[int, int, int]):
    """Set all LEDs to a single color."""
    self.is_flashing = False  # Stop flashing
    
    if self.hardware_available and self.strip:
        converted = self._rgb_to_internal(rgb)
        for i in range(self.count):
            self.strip.setPixelColor(i, Color(converted[0], converted[1], converted[2]))
        self.strip.show()
    
    # Console visualization for testing without hardware
    viz = _visualize_led(rgb)
    logger.info(f"LED set color {viz} RGB{rgb}")
```

## Configuration Extraction

**Code/Server** (hardcoded in multiple places):
```python
# led.py
self.led_count = 4
self.strip = Freenove_RPI_WS281X(4, 255, 'RGB')

# main.py or other
led = Led()  # Creates globally
```

**Rat/** (centralized in config.py):
```python
# config.py - Single source of truth
LED_PIN = 18
LED_COUNT = 4
LED_BRIGHTNESS = 255
LED_COLOR_FORMAT = 'RGB'
LED_PCB_VERSION = 2

# brain_state.py - Uses config
led = get_led_controller(
    pin=config.LED_PIN,
    count=config.LED_COUNT,
    brightness=config.LED_BRIGHTNESS,
    color_format=config.LED_COLOR_FORMAT,
    pcb_version=config.LED_PCB_VERSION
)
```

## Enhanced Features in Rat/

### 1. **Flashing with State Management**
```python
# Code/Server: No built-in flash support (would need polling)

# Rat/: Clean API
led.flash((255, 0, 0), interval=0.5)  # Start flash
# ... in main loop ...
led.update()  # Handles timing automatically
```

### 2. **Local Dependencies**
```python
# Code/Server: Assumes system package
from rpi_ws281x import Adafruit_NeoPixel

# Rat/: Local-first with fallback
# Tries Rat/lib_utils/ first
# Falls back to system package
# Fully offline-capable
```

### 3. **Console Visualization**
```python
# Code/Server: No console feedback without hardware

# Rat/: ANSI colored output even in simulation
# Shows ● for ON, ◯ for OFF
# Shows RGB values
# Logs all state changes
```

### 4. **Type Annotations**
```python
# Code/Server: No type hints

# Rat/: Full typing support
def set_color(self, rgb: Tuple[int, int, int]):
    def _rgb_to_internal(self, rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    def get_led_controller(...) -> LEDController:
```

## API Compatibility

**NOT 100% Compatible** (by design):

Code/Server API:
```python
led = Led()           # Gathers config, detects hardware
led.colorWipe(color) # Wipes color across LEDs (slow)
led.Blink(color)     # All at once
led.wheel(pos)       # Returns single color from wheel
```

Rat/ API:
```python
led = get_led_controller(...)  # Simpler single-shot init
led.set_color(color)           # Direct, all at once
led.flash(color, interval)     # Timed flashing
led.update()                   # Call in loop for timing
led.pulse(color, cycles)       # Pulsing animation
```

**Reasoning**:
- Code/Server methods are named for animation effects (colorWipe)
- Rat/ methods focus on state control (set_color, flash, pulse)
- Rat/ separates animation state (init) from rendering (update)
- Rat/ is designed for state machine (not imperative loops)

## Lessons from Freenove Code

1. **Graceful Degradation is Critical**
   - Code/Server uses `is_support_led_function` flag
   - Rat/ adopts same pattern with `hardware_available` flag
   - Both skip execution if hardware unavailable (no crashes)

2. **Version Detection Should be Simple**
   - Single `/sys/firmware/` check is reliable
   - No need for complex version tables
   - Pi 5 detection very clear/simple

3. **Color Format Mapping Required**
   - Different LED strips have different wiring
   - RGB vs RBG vs GRB very common
   - Must support all 6 permutations

4. **Local Library Vendoring**
   - rpi_ws281x library can be outdated
   - Better to vendor and update locally
   - Offline capability important for embedded systems

5. **Separation of Concerns**
   - Parameter detection (separate class in Code/Server)
   - LED control (separate class)
   - Makes testing and reuse easier

## Migration Summary

| Aspect | Code/Server | Rat/ | Status |
|--------|-------------|------|--------|
| Pi version detection | ✓ | ✓ Integrated | ✅ Same |
| PCB compatibility | ✓ | ✓ Integrated | ✅ Same |
| Local dependencies | ✗ System only | ✓ Local first | ✅ Improved |
| Graceful fallback | ✓ | ✓ | ✅ Same |
| Console visualization | ✗ | ✓ ANSI colors | ✅ NEW |
| Configuration centralization | ✗ Hardcoded | ✓ config.py | ✅ NEW |
| Type annotations | ✗ | ✓ Full typing | ✅ NEW |
| Flashing API | ✗ Manual | ✓ Built-in | ✅ NEW |
| Pulse animation | ✗ | ✓ | ✅ NEW |
| Singleton pattern | ✗ Global instance | ✓ get_led_controller() | ✅ NEW |

**Conclusion**: Rat/ takes the proven Freenove approach and modernizes it with better architecture, local dependencies, and enhanced features while maintaining the robust error handling that makes Code/Server reliable.

