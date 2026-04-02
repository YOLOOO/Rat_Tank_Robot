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
COMMAND_TIMEOUT = 1.0  # seconds
MAX_COMMAND_QUEUE_SIZE = 100

# ============================================================================
# ROBOT BEHAVIOR REGISTRY
# ============================================================================
# Behaviors are discovered and registered here
# Format: {name: (module_path, color_tuple, display_order)}
BEHAVIORS = {
    "IDLE": (None, (0, 255, 0), 0),  # Green - default idle state
    "TEST": ("behavior_scripts.test", (255, 165, 0), 1),  # Orange - hardware testing
}

# ============================================================================
# MISSION REGISTRY
# ============================================================================
# Format: {name: (module_path, color_tuple, display_order)}
MISSIONS = {
    #"WARS": ("missions.robot_wars", (255, 0, 0), 1),  # Red
    #"OBSTACLE": ("missions.obstacle_course", (255, 165, 0), 2),  # Orange
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
# Pin assignments for motor control (gpiozero.Motor uses forward/backward pin pairs)
# Reference: Code/Server/motor.py
MOTOR_LEFT_FORWARD = 24
MOTOR_LEFT_BACKWARD = 23
MOTOR_RIGHT_FORWARD = 5
MOTOR_RIGHT_BACKWARD = 6
MOTOR_PWM_FREQ = 1000  # Hz

# Default motor speeds
MOTOR_SPEED_NORMAL = 100  # 0-255
MOTOR_SPEED_SLOW = 50
MOTOR_SPEED_FAST = 200

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
SERVO_CH0_MIN = 90
SERVO_CH0_MAX = 150
SERVO_CH1_MIN = 90
SERVO_CH1_MAX = 150
SERVO_CH2_MIN = 0
SERVO_CH2_MAX = 180

# PCB version for servo control (same as LED PCB version)
SERVO_PCB_VERSION = 2

# ============================================================================
# SENSOR CONFIGURATION
# ============================================================================
DISTANCE_SENSOR_PIN = 17  # GPIO pin for distance sensor
TRACKING_SENSOR_PIN = 27  # GPIO pin for tracking sensor

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
# SELECTION MENU ORDER
# ============================================================================
# Order items appear in the selection menu (IDLE state)
MENU_ITEMS = list(BEHAVIORS.keys()) + list(MISSIONS.keys())
