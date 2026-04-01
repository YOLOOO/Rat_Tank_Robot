#!/bin/bash
#
# START RAT BRAIN
# ===============
# Starts the robot brain server on Raspberry Pi
#
# IMPORTANT for Pi 5 + PCB v2:
# The pigpiod daemon must be running for servo control!
# This script will attempt to start it if needed.
#

set -e

echo "=========================================="
echo "RAT BRAIN - Starting Robot"
echo "=========================================="

# Get script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Optional: Set up Python path
export PYTHONPATH="${PYTHONPATH}:$DIR"

# For Pi 5 + PCB v2: Start pigpiod daemon if not running
echo "Checking pigpiod daemon (required for servo control)..."
if ! pgrep -x "pigpiod" > /dev/null; then
    echo "Starting pigpiod daemon..."
    sudo pigpiod -l -s 1 >/dev/null 2>&1 &
    sleep 2
    echo "✓ pigpiod daemon started"
else
    echo "✓ pigpiod daemon already running"
fi
echo ""

# Start the brain in background
echo "Starting RAT BRAIN server..."
python3 rat_brain/brain_state.py &
BRAIN_PID=$!

echo "Brain PID: $BRAIN_PID"
echo ""
echo "RAT BRAIN is running!"
echo "Connect controller with: python3 controller_sender_client.py --host <ROBOT_IP>"
echo ""
echo "To stop: ./stop_rat.sh"
echo ""

# Keep script alive
wait $BRAIN_PID
