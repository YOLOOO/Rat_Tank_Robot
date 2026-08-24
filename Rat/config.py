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
ROBOT_IP = "192.168.137.180"  # IP address of the robot
COMMAND_TIMEOUT = 1.0  # seconds
MAX_COMMAND_QUEUE_SIZE = 100

# ============================================================================
# MISSION REGISTRY
# ============================================================================
# Selectable missions shown in the IDLE menu.
# Behaviors (behavior_scripts/) are building blocks used by missions — not registered here.
# Format: {name: (module_path, color_tuple, display_order)}
MISSIONS = {
    "MOTION_TEST":    ("missions.motion_indication_test", (255, 0,   0),   1),  # Red     - LED/servo/motor test
    "SENSORY_TEST":   ("missions.sensory_test",           (0,   255, 0),   2),  # Green   - sensor readout test
    "REMOTE_CONTROL": ("missions.remote_control",         (0,   0,   255), 3),  # Blue    - controller control
    "CAMERA_TEST":    ("missions.camera_test",            (255, 0,   255), 4),  # Magenta - camera test
    "AI_CONTROLLED":  ("missions.AI_controlled",          (0,   100, 255), 5),  # Cyan-blue - LLM-driven autonomy
}

# ============================================================================
# LED CONFIGURATION
# ============================================================================
# Freenove FNK0077 Tank: 4 LEDs on Raspberry Pi 5 with PCB v2 (SPI, GRB format)
LED_PIN = 18  # GPIO pin for LED strip (not used for SPI, kept for reference)
LED_COUNT = 4  # Number of LEDs (Freenove tank has 4)
LED_BRIGHTNESS = 255  # Max brightness 0-255
LED_FLASH_INTERVAL = 0.5  # seconds
LED_PCB_VERSION = 2  # PCB version (2 for Pi 5 SPI, 1 for older Pi RPI_WS281X)
LED_COLOR_FORMAT = 'GRB'  # SPI PCB v2 uses GRB, RPI_WS281X uses RGB

# LED Colors (RGB)
LED_COLORS = {
    "idle": (0, 255, 0),  # Green
    "running": (0, 100, 255),  # Blue
    "error": (255, 0, 0),  # Red
    "selection": (255, 255, 0),  # Yellow
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
CAMERA_STREAM_PORT = 8888
CAMERA_STREAM_HOST = "0.0.0.0"

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
AI_CAMERA_RATE          = 2.0           # Seconds between camera snapshots (0 = disabled)
AI_CAMERA_SIZE          = (320, 240)    # Snapshot resolution for LLM consumption
AI_CAMERA_JPEG_QUALITY  = 70            # JPEG quality for snapshots (lower = smaller payload)

# Below this, any command that would drive a track forward is blocked.
# Checked in two places: AI_controlled.py's onboard interlock (every ~50ms
# tick, using the live sensor reading, regardless of what the dev PC sent)
# and AI_controller_client.py's client-side override (once per LLM
# decision). The onboard check is the one that actually matters for not
# hitting things — the client-side one only catches it a decision earlier.
AI_MIN_OBSTACLE_CM      = 10

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

