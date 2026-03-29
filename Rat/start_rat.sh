#!/bin/bash
#
# START RAT BRAIN
# ===============
# Starts the robot brain server on Raspberry Pi
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
