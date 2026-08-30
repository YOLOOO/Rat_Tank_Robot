"""
RAT BRAIN - Central Configuration
================================
Single source of truth for all system settings.
"""

# ============================================================================
# NETWORK CONFIGURATION
# ============================================================================
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5577
ROBOT_IP = "192.168.137.140"  # IP address of the robot
COMMAND_TIMEOUT = 1.0  # seconds
MAX_COMMAND_QUEUE_SIZE = 100

# ============================================================================
# LED CONFIGURATION
# ============================================================================
# Freenove FNK0077 Tank: 4 LEDs on Raspberry Pi 5 (SPI, GRB format)
LED_COUNT = 4  # Number of LEDs (Freenove tank has 4)
LED_BRIGHTNESS = 255  # Max brightness 0-255
LED_COLOR_FORMAT = 'GRB'  # SPI color sequence

# LED color palette — every LED color used anywhere in the system is defined
# once here (see behavior_scripts/led/patterns.py for the behaviors that
# consume them: static/off/blink/blend/spin). Nothing outside this section
# should hardcode a color tuple.
LED_COLOR_IDLE          = (0,   255, 0)    # green  - brain idle / menu default
LED_COLOR_ERROR         = (255, 0,   0)    # red    - brain ERROR state
LED_COLOR_CRITICAL      = (255, 0,   0)    # red    - mission-level hard failure (e.g. camera_test step fail)
LED_COLOR_CONNECTED     = (0,   100, 255)  # blue   - active link / activity (AI spin while dev PC connected)
LED_COLOR_DISCONNECTED  = (255, 80,  0)    # amber  - TCP link lost (kept distinct from LED_COLOR_ERROR: brain
                                            #          fault and dev-PC disconnect must be visually distinguishable)

# Mission identity colors — shown on menu highlight and while that mission
# runs. Red and green are reserved exclusively for error/OK signaling (see
# LED_COLOR_ERROR/CRITICAL/DISCONNECTED and LED_COLOR_IDLE above) — no
# mission identity color may be pure red or pure green.
LED_COLOR_MOTION_TEST    = (255, 165, 0)   # orange
LED_COLOR_SENSORY_TEST   = (255, 255, 0)   # yellow
LED_COLOR_CAMERA_TEST    = (255, 0,   255) # magenta
LED_COLOR_REMOTE_CONTROL = (0,   0,   255) # blue
LED_COLOR_AI_CONTROLLED  = (0,   100, 255) # blue (distinct shade from REMOTE_CONTROL)

# Blink/blend timing defaults (behavior_scripts/led/patterns.py)
LED_BLINK_ON_S       = 0.15  # fast blink half-period — one-shot fault alerts (flash_alert)
LED_BLINK_OFF_S      = 0.15
LED_BLINK_DURATION_S = 1.5   # how long a one-shot error blink runs before settling
LED_MENU_FLASH_S     = 0.15  # brief LED_COLOR_IDLE flash brain_state.py shows when returning to mission-select

# Slower blink for continuous "mission actively running" indicators (sensory_test,
# remote_control while connected) — distinct cadence from the fast fault blink above
# so a viewer can tell "working normally" apart from "something's wrong" at a glance.
LED_ACTIVITY_BLINK_ON_S  = 0.4
LED_ACTIVITY_BLINK_OFF_S = 0.4

# ============================================================================
# MISSION REGISTRY
# ============================================================================
# Selectable missions shown in the IDLE menu.
# Behaviors (behavior_scripts/) are building blocks used by missions — not registered here.
# Format: {name: (module_path, color_tuple, display_order)}
MISSIONS = {
    "MOTION_TEST":    ("missions.motion_indication_test", LED_COLOR_MOTION_TEST,    1),  # LED/servo/motor test
    "SENSORY_TEST":   ("missions.sensory_test",           LED_COLOR_SENSORY_TEST,   2),  # sensor readout test
    "CAMERA_TEST":    ("missions.camera_test",            LED_COLOR_CAMERA_TEST,    3),  # camera test
    "REMOTE_CONTROL": ("missions.remote_control",         LED_COLOR_REMOTE_CONTROL, 4),  # controller control
    "AI_CONTROLLED":  ("missions.AI_controlled",          LED_COLOR_AI_CONTROLLED,  5),  # LLM-driven autonomy
}

# ============================================================================
# MOTOR CONFIGURATION
# ============================================================================
# Pin assignments — Freenove FNK0077 V2.0
# M1 (left track) : GPIO23 (+), GPIO24 (-)
# M2 (right track) : GPIO6  (+), GPIO5  (-)
MOTOR_LEFT_PLUS  = 23
MOTOR_LEFT_MINUS = 24
MOTOR_RIGHT_PLUS = 6
MOTOR_RIGHT_MINUS = 5
MOTOR_PWM_FREQ = 1000  # Hz

# Duty range: -4095 (full reverse) to +4095 (full forward)
MOTOR_MAX_DUTY = 4095
MOTOR_SPEED_NORMAL = 2048
MOTOR_SPEED_SLOW   = 1024
MOTOR_SPEED_FAST   = 3500

# A stopped tank track commonly can't overcome static friction below ~35-50%
# PWM duty, even though it can sustain motion at a lower duty once rolling.
# MOTOR_SPEED_SLOW (1024/4095 = 25%) is below that threshold, so starting
# from a stop at :SLOW would silently just sit there. Below this fraction of
# MOTOR_MAX_DUTY, a motor starting from 0 gets a brief kick first.
MOTOR_KICKSTART_THRESHOLD = 0.35
MOTOR_KICKSTART_MS        = 120
# Kick at a fraction of full duty rather than literally 100% — enough to
# break static friction without doubling the worst-case simultaneous current
# draw when both tracks kick together (a real brownout risk on a shared
# battery/regulator — a full system freeze, SSH included, is the symptom).
MOTOR_KICKSTART_DUTY      = 0.75

# Reversing a spinning track straight into the opposite direction
# (plug-braking) draws more current than starting from a stop — often the
# single biggest current spike a motor driver sees. Force a brief settle at
# zero duty before honoring any command that flips a track's sign. This is
# also the "grace period" for an upstream controller (e.g. the AI loop)
# that changes its mind rapidly — it's enforced here, once, for every
# caller, rather than trusted to each mission.
MOTOR_REVERSAL_SETTLE_MS  = 150

# Turn calibration — degrees the robot rotates per second at MOTOR_SPEED_NORMAL
# Tune this on your actual surface
MOTOR_DEGREES_PER_SECOND = 180.0

# ============================================================================
# SERVO CONFIGURATION
# ============================================================================
# Pin assignments for servo control (PCB v2)
SERVO_CHANNEL_0 = 7   # GPIO 7 - servo 0 (e.g., pan)
SERVO_CHANNEL_1 = 8   # GPIO 8 - servo 1 (e.g., tilt)
SERVO_CHANNEL_2 = 25  # GPIO 25 - servo 2 (optional, reserved)
SERVO_PWM_FREQ = 50   # Hz (standard servo frequency)

# Channel-specific angle limits.
# CH0 (arm): MIN=150 is the DOWN position, MAX=70 is UP — physically inverted.
# CH1 (grip): MIN=80 is OPEN, MAX=155 is CLOSED — normal direction.
# All consumers use _servo_clamp() which handles MIN > MAX correctly.
SERVO_CH0_MIN = 150
SERVO_CH0_MAX = 70
SERVO_CH1_MIN = 80
SERVO_CH1_MAX = 155

# PCB version for servo control (same as LED PCB version)
SERVO_PCB_VERSION = 2

# Servo move speed tiers (behavior_scripts/servo/ramp.py) — seconds for a
# *full* 0-180 degree sweep at each tier; an actual move's duration scales
# down proportionally to the angle it's actually travelling (see that
# module's duration_for()). Time-interpolated per brain tick, not
# sleep-based, so it's safe to drive from any mission's per-tick run(),
# AI_controlled.py included, without ever stalling that tick.
# See MOTOR_SENSORY_REWORK_2026-08-29 in git history for the related
# motor-side wrapper work this follows the same pattern as.
SERVO_MOVE_FULL_SWEEP_SLOW_S = 3.0
SERVO_MOVE_FULL_SWEEP_MID_S  = 1.2
SERVO_MOVE_FULL_SWEEP_FAST_S = 0.4
SERVO_MOVE_DEFAULT_SPEED     = "MID"  # tier used when no :SLOW/:MID/:FAST modifier is given

# Uniform servo shutdown (rat_brain/brain_state.py's _park_and_stop_servos(),
# called from _stop_mission() on every mission exit — HALT or a mission
# ending on its own, not HALT-only). Eases both channels to this rest
# position using the same time-interpolated servo_ramp.step() every other
# servo move in the codebase already uses, then cuts PWM entirely. Arm
# parks UP rather than down — parked down sits right in front of the
# ultrasonic sensor and would occlude it.
#
# Paced, not instant: a servo left de-energized during a servo-less mission
# (camera_test, sensory_test) has zero holding torque and can droop under
# gravity for the mission's whole duration with no software ever noticing —
# this is open-loop, there's no position feedback, only the last angle we
# commanded. An instant setServoPwm() to the park angle used to close
# whatever gap that drooping left in one full-power step — a hard slam, not
# a gentle correction. Since we can't know the real starting angle, the ramp
# always assumes the pessimistic worst case (the channel's opposite
# extreme) and paces the move over that full-range duration; if the actual
# droop was smaller, the servo just reaches target early and sits there for
# the rest of the ramp — harmless either way.
#
# Only cutting power *after* it settles still matters: previously only HALT
# de-energized the servo at all — a mission ending on its own (GOAL_REACHED,
# STUCK, TIMEOUT, SENSOR_FAULT, or motion_indication_test finishing its
# sequence) left it energized and holding position indefinitely, a
# sustained current draw on the same shared rail MOTOR_KICKSTART_DUTY above
# already treats as a brownout risk.
SERVO_PARK_ARM_ANGLE  = SERVO_CH0_MAX   # up — clear of the ultrasonic sensor
SERVO_PARK_GRIP_ANGLE = SERVO_CH1_MAX   # closed
SERVO_PARK_SPEED      = "MID"           # speed tier (see SERVO_MOVE_FULL_SWEEP_*) for the worst-case-bounded park ramp

# ============================================================================
# SENSOR CONFIGURATION
# ============================================================================
DISTANCE_SENSOR_PIN = 17  # GPIO pin for distance sensor
TRACKING_SENSOR_PIN = 27  # GPIO pin for tracking sensor

# Infrared line sensors — GPIO pins vary by PCB version
INFRARED_PCB_VERSION = 2  # 1 = older Pi, 2 = Pi 5 (Freenove FNK0077 V2.0)

# Raspberry Pi hardware generation — used to select driver backends
# 1 = Pi 4 or earlier (gpiozero), 2 = Pi 5 (lgpio/hardware PWM)
# To detect at runtime: subprocess.run(['cat', '/sys/firmware/devicetree/base/model'])
#   "Raspberry Pi 5" in output → 2, else → 1
PI_VERSION = 2

# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR
EMERGENCY_STOP_PIN = 26  # Optional: GPIO for emergency stop button

# ============================================================================
# TIMING CONFIGURATION
# ============================================================================
STATE_UPDATE_INTERVAL = 0.05  # 50ms - main loop tick
COMMAND_POLL_INTERVAL = 0.01  # 10ms - check for new commands
MOTOR_SAFETY_TIMEOUT = 10.0  # seconds - max time a behavior can run

#=============================================================================
# CAMERA CONFIGURATION
#=============================================================================
CAMERA_TEST_PHOTO  = "/home/rat/test_photo/camera_test.jpg"

# ============================================================================
# KEYBOARD REMOTE DRIVE  (dev PC side)
# ============================================================================
# Motor duty used for W/A/S/D drive commands in controller_sender_client.py
KEYBOARD_DRIVE_SPEED = MOTOR_SPEED_FAST

# ============================================================================
# AI CONTROLLER CONFIGURATION
# ============================================================================
# Robot side: missions/AI_controlled.py    Dev PC side: AI_controller_client.py
AI_TELEMETRY_PORT       = 5578          # Robot → Dev PC telemetry channel
AI_TELEMETRY_RATE       = 0.2           # Seconds between telemetry sends (5 Hz)
# Matched to AI_LOOP_RATE so a fresh frame is normally ready by the time the
# LLM loop wants one, without adding wait-for-fresh-frame logic to the loop
# itself — the loop still just reads whatever the snapshot thread last
# captured (see _snapshot_loop()), it's just rarely more than one tick stale.
AI_CAMERA_RATE          = 1.0           # Seconds between camera snapshots (0 = disabled)
AI_CAMERA_SIZE          = (320, 240)    # Snapshot resolution for LLM consumption
AI_CAMERA_JPEG_QUALITY  = 70            # JPEG quality for snapshots (lower = smaller payload)

# Below this, any command that would drive a track forward is blocked.
# Checked in two places: AI_controlled.py's onboard interlock (every ~50ms
# tick, using the live sensor reading, regardless of what the dev PC sent)
# and AI_controller_client.py's client-side override (once per LLM
# decision). The onboard check is the one that actually matters for not
# hitting things — the client-side one only catches it a decision earlier.
AI_MIN_OBSTACLE_CM      = 10

# Sensor sanity (missions/AI_controlled.py) — pre-flight check before motors/
# threads arm, and a continuous check once running. AI_PREFLIGHT_READS is a
# handful of back-to-back reads (fast when the sensor is healthy; each read
# can itself take up to ~1s on the ultrasonic's own echo timeout, so a
# genuinely dead sensor takes a few seconds to fail out — that's the
# exception path, not the common case). AI_SENSOR_FAULT_TIMEOUT_S is how
# long a sensor can keep erroring once already running before it's treated
# as dead rather than momentarily noisy.
AI_PREFLIGHT_READS         = 3
AI_SENSOR_FAULT_TIMEOUT_S  = 5.0
# How long the LLM can keep re-issuing a forward/curve move that the onboard
# interlock keeps blocking before the mission gives up and reports STUCK
# instead of idling in front of the obstacle forever.
AI_STUCK_TIMEOUT_S         = 15.0

AI_OLLAMA_HOST          = "http://localhost:11434"
AI_DEFAULT_MODEL        = "llava"       # Any Ollama model; vision models receive images
AI_LOOP_RATE            = 1.0           # Seconds between LLM calls (1 Hz default)
AI_COMMAND_HISTORY      = 5             # How many past actions to include in LLM context
AI_OLLAMA_TIMEOUT       = 60.0          # HTTP timeout for /api/generate — local model cold-starts
                                         # (especially vision models) routinely take well over 15s
AI_HEARTBEAT_INTERVAL   = 5.0           # Seconds between keepalive bytes on the command channel —
                                         # keeps it under the robot's CLIENT_IDLE_TIMEOUT (15s) even
                                         # when a single Ollama call takes longer than that to return

# Robot-side status LED (missions/AI_controlled.py)
AI_LED_SPIN_INTERVAL    = 0.15          # Seconds between spin steps on the 4-LED "waiting on LLM" chase
AI_UNRESPONSIVE_WINDOW  = 5.0           # Seconds a tick error keeps the status LED solid red

# Goal system (dev PC sends AI_CMD:GOAL:<dist_cm>:<ir>:<tolerance_cm>:<max_duration_s>
# once, right after selecting AI_CONTROLLED; robot evaluates it every tick and
# reports a terminal status — GOAL_REACHED / STUCK / TIMEOUT / SENSOR_FAULT —
# back over telemetry). These are CLI defaults for AI_controller_client.py /
# ./start_ai, not robot-side config — None means "no goal on that axis" and
# is sent to the robot as -1.
AI_DEFAULT_TASK      = "Find a small object, navigate to it, lift it with the robot arm."
AI_GOAL_DISTANCE_CM  = None    # Default --goal-distance-cm
AI_GOAL_IR           = None    # Default --goal-ir (0-7 bitmask: left<<2 | center<<1 | right)
AI_GOAL_TOLERANCE_CM = 5.0     # Default --goal-tolerance-cm
AI_MAX_DURATION_S    = 20.0     # Default --max-duration-s (0 = disabled)

