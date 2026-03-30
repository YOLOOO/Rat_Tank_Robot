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
    "DANCE": ("behavior_scripts.dance_demo", (255, 0, 255), 1),  # Magenta
    "PATROL": ("behavior_scripts.patrol", (0, 0, 255), 2),  # Blue
    "SCAN": ("behavior_scripts.toy_car_picker", (255, 255, 0), 3),  # Yellow
}

# ============================================================================
# MISSION REGISTRY
# ============================================================================
# Format: {name: (module_path, color_tuple, display_order)}
MISSIONS = {
    "WARS": ("missions.robot_wars", (255, 0, 0), 1),  # Red
    "OBSTACLE": ("missions.obstacle_course", (255, 165, 0), 2),  # Orange
}

# ============================================================================
# LED CONFIGURATION
# ============================================================================
# Freenove FNK0077 Tank: 4 LEDs on GPIO pin 18
LED_PIN = 18  # GPIO pin for LED strip (GPIO_GEN1)
LED_COUNT = 4  # Number of LEDs (Freenove tank has 4)
LED_BRIGHTNESS = 255  # Max brightness 0-255
LED_FLASH_INTERVAL = 0.5  # seconds
LED_PCB_VERSION = 2  # PCB version (2 for Pi 5, 1 for older Pi)
LED_COLOR_FORMAT = 'RGB'  # RGB sequence type ('RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR')

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
# Pin assignments for motor control
MOTOR_LEFT_FORWARD = 12
MOTOR_LEFT_BACKWARD = 11
MOTOR_RIGHT_FORWARD = 8
MOTOR_RIGHT_BACKWARD = 7
MOTOR_PWM_FREQ = 1000  # Hz

# Default motor speeds
MOTOR_SPEED_NORMAL = 100  # 0-255
MOTOR_SPEED_SLOW = 50
MOTOR_SPEED_FAST = 200

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
