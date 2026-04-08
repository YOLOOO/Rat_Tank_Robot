#!/bin/bash
#
# STOP RAT BRAIN
# ==============
# Stops the robot brain server and ensures motors and LEDs are off.
# Uses SIGINT so Python's KeyboardInterrupt handler fires and cleanup() runs.
#

echo "=========================================="
echo "RAT BRAIN - Stopping Robot"
echo "=========================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Stopping RAT BRAIN..."

pkill -SIGINT -f "python3.*brain_state.py" || true

# Give cleanup() time to run (motors off, LEDs off, sockets closed)
sleep 2

echo ""
echo "RAT BRAIN stopped."
echo ""
