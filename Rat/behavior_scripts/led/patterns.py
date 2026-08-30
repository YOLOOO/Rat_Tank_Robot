"""behavior_scripts/led/patterns.py

Non-blocking, time-derived LED behaviors for the 4-LED status ring —
generalizes the ad hoc patterns already proven by motion_indication_test.py's
color-cycle self-test phase and AI_controlled.py's spin/red-alert status LED.

Same ownership model as behavior_scripts/servo/ramp.py: callers own all
pattern state themselves (just a start_time, as a plain value in their own
module global or loop-local variable) — this module holds none. Every
step_*() function derives its current output purely from
`time.time() - start_time`, so calling it more or less often never desyncs
the pattern, and there is no counter to reset between calls.

Five behaviors:
    static(color)                                  - solid on, all LEDs, one-shot
    off()                                           - all LEDs off, one-shot
    step_blink(color, on_s, off_s, start_time)      - on/off blink, returns whether currently lit
    step_blend(color_a, color_b, period_s, start_time) - smooth crossfade between two colors (breathing)
    step_spin(color, interval_s, start_time)        - chases one lit LED around the ring, returns its index

Plus one blocking convenience built from step_blink — flash_alert() — for the
common "mission is ending on a fault, briefly grab attention before the brain
takes the LED back" case. Everything else here is non-blocking and meant to
be called once per brain tick; flash_alert() is the one exception.

Colors are plain (r, g, b) tuples — see config.LED_COLOR_* for the named
palette callers should be drawing from, so every color in the system stays
defined in exactly one place.
"""

import time

import config
from common_hardware import get_led_controller


def static(color):
    """Solid on, all LEDs, one-shot — no timing state needed."""
    get_led_controller().set_all_led_rgb(list(color))


def off():
    """All LEDs off, one-shot."""
    get_led_controller().set_all_led_rgb([0, 0, 0])


def step_blink(color, on_s: float, off_s: float, start_time: float) -> bool:
    """Advances one tick's worth of a blink cycle. Returns True if the LEDs
    are currently lit (color) this tick, False if currently off."""
    period = on_s + off_s
    phase = (time.time() - start_time) % period
    lit = phase < on_s

    led = get_led_controller()
    if lit:
        led.set_all_led_rgb(list(color))
    else:
        led.set_all_led_rgb([0, 0, 0])
    return lit


def step_blend(color_a, color_b, period_s: float, start_time: float) -> tuple:
    """Advances one tick's worth of a breathing crossfade between two colors —
    a triangle wave over period_s: color_a -> color_b -> color_a. Returns the
    blended (r, g, b) currently shown."""
    if period_s <= 0:
        get_led_controller().set_all_led_rgb(list(color_a))
        return tuple(color_a)

    phase = (time.time() - start_time) % period_s
    half = period_s / 2.0
    # 0.0 at phase=0 and phase=period_s, 1.0 at phase=half — triangle wave
    progress = phase / half if phase <= half else (period_s - phase) / half

    blended = tuple(
        round(a + (b - a) * progress) for a, b in zip(color_a, color_b)
    )
    get_led_controller().set_all_led_rgb(list(blended))
    return blended


def step_spin(color, interval_s: float, start_time: float) -> int:
    """Advances one tick's worth of a chase — one LED lit at a time, moving
    around the ring every interval_s. Returns the currently lit index."""
    idx = int((time.time() - start_time) / interval_s) % config.LED_COUNT

    led = get_led_controller()
    led.set_all_led_rgb_data([0, 0, 0])
    led.set_led_rgb(idx, list(color))
    return idx


def flash_alert(color, on_s: float, off_s: float, duration_s: float):
    """Blocking one-shot alert: blinks `color` for duration_s, then settles
    solid on that color. For a brief, attention-grabbing fault signal at a
    point where blocking briefly is acceptable (mission ending/erroring) —
    never call this from inside a long-running per-tick loop."""
    start = time.time()
    while time.time() - start < duration_s:
        step_blink(color, on_s, off_s, start)
        time.sleep(0.05)
    static(color)
