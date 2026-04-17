#!/bin/bash
#
# STOP RAT BRAIN
# ==============
# Stops the robot brain and ensures motors and LEDs are left off.
# Reads PID from rat_brain.pid (written by start_rat.sh).
# Escalates: SIGINT → SIGTERM → SIGKILL with verification at each step.
#

echo "=========================================="
echo "RAT BRAIN - Stopping Robot"
echo "=========================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="$DIR/rat_brain.pid"

# --- Resolve the PID ----------------------------------------------------------

BRAIN_PID=""

if [ -f "$PID_FILE" ]; then
    BRAIN_PID=$(cat "$PID_FILE")
    if ! kill -0 "$BRAIN_PID" 2>/dev/null; then
        echo "RAT BRAIN is not running (stale PID file)."
        rm -f "$PID_FILE"
        echo ""
        exit 0
    fi
else
    # Fallback: pgrep in case the PID file is missing
    BRAIN_PID=$(pgrep -f "python3.*brain_state.py" | head -1)
    if [ -z "$BRAIN_PID" ]; then
        echo "RAT BRAIN is not running."
        echo ""
        exit 0
    fi
    echo "WARNING: No PID file found — resolved via pgrep (PID $BRAIN_PID)"
fi

echo "Stopping PID $BRAIN_PID..."

# --- SIGINT (clean shutdown via Python signal handler) ------------------------

echo "Sending SIGINT..."
kill -SIGINT "$BRAIN_PID" 2>/dev/null || true
sleep 3

if ! kill -0 "$BRAIN_PID" 2>/dev/null; then
    echo "RAT BRAIN stopped cleanly."
    rm -f "$PID_FILE"
    echo ""
    exit 0
fi

# --- SIGTERM ------------------------------------------------------------------

echo "Still running — sending SIGTERM..."
kill -SIGTERM "$BRAIN_PID" 2>/dev/null || true
sleep 2

if ! kill -0 "$BRAIN_PID" 2>/dev/null; then
    echo "RAT BRAIN stopped."
    rm -f "$PID_FILE"
    echo ""
    exit 0
fi

# --- SIGKILL ------------------------------------------------------------------

echo "Still running — sending SIGKILL..."
kill -SIGKILL "$BRAIN_PID" 2>/dev/null || true
sleep 1

if kill -0 "$BRAIN_PID" 2>/dev/null; then
    echo "WARNING: RAT BRAIN could not be killed (PID $BRAIN_PID)."
    exit 1
fi

echo "RAT BRAIN killed."
rm -f "$PID_FILE"
echo ""
