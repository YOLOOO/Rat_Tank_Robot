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
ROBOT_IP = "192.168.0.237"  # IP address of the robot
COMMAND_TIMEOUT = 1.0  # seconds
MAX_COMMAND_QUEUE_SIZE = 100

# ============================================================================
# MISSION REGISTRY
# ============================================================================
# Selectable missions shown in the IDLE menu.
# Behaviors (behavior_scripts/) are building blocks used by missions — not registered here.
# Format: {name: (module_path, color_tuple, display_order)}
MISSIONS = {
    "TEST":           ("missions.test",           (255, 165, 0), 1),  # Orange - hardware test
    "REMOTE_CONTROL": ("missions.remote_control", (0, 100, 255), 2),  # Blue   - trackball control
    #"WARS":     ("missions.robot_wars",      (255, 0, 0),   3),  # Red
    #"OBSTACLE": ("missions.obstacle_course", (255, 165, 0), 4),  # Orange
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

# Default servo angles (0-180)
SERVO_CENTER_ANGLE = 90
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180

# Channel-specific angle limits (if different)
SERVO_CH0_MIN = 150
SERVO_CH0_MAX = 70
SERVO_CH1_MIN = 70
SERVO_CH1_MAX = 160

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
DEBUG = True
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
EMERGENCY_STOP_PIN = 26  # Optional: GPIO for emergency stop button

# ============================================================================
# TIMING CONFIGURATION
# ============================================================================
STATE_UPDATE_INTERVAL = 0.05  # 50ms - main loop tick
COMMAND_POLL_INTERVAL = 0.01  # 10ms - check for new commands
MOTOR_SAFETY_TIMEOUT = 10.0  # seconds - max time a behavior can run

# ============================================================================
# MNT TRACKBALL CONTROLLER  (dev PC side)
# ============================================================================
# evdev device name to match — run `python -m evdev.evtest` to find yours
MNT_DEVICE_NAME     = "MNT Research Reform Trackball (RP2040)"

# How many MOTOR commands to send per second (avoids flooding the TCP connection)
MNT_SEND_RATE       = 30   # Hz

# Ignore ball movement below this raw delta (reduces jitter when ball is still)
MNT_DEADZONE        = 2

# Multiplier applied to raw ball delta before mapping to motor duty
# Higher = more responsive, lower = easier fine control
MNT_SPEED_SCALE     = 55.0

# Maximum motor duty the trackball can command (keeps a speed ceiling)
MNT_MAX_DUTY        = 3500

