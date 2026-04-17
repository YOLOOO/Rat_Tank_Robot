#!/bin/bash
#
# START RAT BRAIN
# ===============
# Starts the robot brain server on Raspberry Pi.
# Runs detached — terminal is free immediately after launch.
# Output is logged to rat_brain.log in this directory.
#
# Usage:
#   ./start_rat.sh          — start the brain
#   tail -f rat_brain.log   — watch live output
#   ./stop_rat.sh           — stop the brain cleanly
#

echo "=========================================="
echo "RAT BRAIN - Starting Robot"
echo "=========================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export PYTHONPATH="${PYTHONPATH}:$DIR"

# Check pigpiod daemon (required for servo control on Pi 5 + PCB v2)
echo "Checking pigpiod daemon..."
if ! pgrep -x "pigpiod" > /dev/null; then
    echo "Starting pigpiod daemon..."
    sudo pigpiod -l -s 1 >/dev/null 2>&1 &
    sleep 2
    echo "pigpiod started"
else
    echo "pigpiod already running"
fi
echo ""

# Start brain detached, log to file
echo "Starting RAT BRAIN..."
nohup python3 rat_brain/brain_state.py > rat_brain.log 2>&1 &
BRAIN_PID=$!
echo "$BRAIN_PID" > rat_brain.pid

echo "Brain PID: $BRAIN_PID"
echo ""
echo "RAT BRAIN is running."
echo ""
echo "  Watch output : tail -f rat_brain.log"
echo "  Stop brain   : ./stop_rat.sh"
echo ""
