#!/bin/bash
#
# STOP RAT BRAIN
# ==============
# Stops the robot brain and ensures motors and LEDs are left off.
# Escalates: SIGINT → SIGTERM → SIGKILL with verification at each step.
#

echo "=========================================="
echo "RAT BRAIN - Stopping Robot"
echo "=========================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if ! pgrep -f "python3.*brain_state.py" > /dev/null 2>&1; then
    echo "RAT BRAIN is not running."
    echo ""
    exit 0
fi

echo "Sending SIGINT (clean shutdown)..."
pkill -SIGINT -f "python3.*brain_state.py" || true
sleep 3

if ! pgrep -f "python3.*brain_state.py" > /dev/null 2>&1; then
    echo "RAT BRAIN stopped cleanly."
    echo ""
    exit 0
fi

echo "Still running — sending SIGTERM..."
pkill -SIGTERM -f "python3.*brain_state.py" || true
sleep 2

if ! pgrep -f "python3.*brain_state.py" > /dev/null 2>&1; then
    echo "RAT BRAIN stopped."
    echo ""
    exit 0
fi

echo "Still running — sending SIGKILL..."
pkill -SIGKILL -f "python3.*brain_state.py" || true
sleep 1

if pgrep -f "python3.*brain_state.py" > /dev/null 2>&1; then
    echo "WARNING: RAT BRAIN could not be killed."
    exit 1
fi

echo "RAT BRAIN killed."
echo ""
