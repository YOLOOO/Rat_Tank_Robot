#!/bin/bash
#
# STOP RAT BRAIN
# ==============
# Stops the robot brain server and ensures motors are off
#

echo "=========================================="
echo "RAT BRAIN - Stopping Robot"
echo "=========================================="

# Get script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Stopping RAT BRAIN..."

# Kill Python processes related to brain
pkill -f "python3.*brain_state.py" || true
pkill -f "python3.*control_receiver" || true

# Give GPIO time to cleanup
sleep 1

echo ""
echo "RAT BRAIN stopped."
echo "Motors OFF"
echo "LEDs OFF"
echo ""
