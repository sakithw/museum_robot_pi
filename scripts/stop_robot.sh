#!/bin/bash
# ============================================================
# stop_robot.sh — Stop all robot processes cleanly
# ============================================================

LOG_DIR=~/robot_logs

echo "Stopping Museum Robot..."

# Kill by saved PIDs
if [ -f "$LOG_DIR/pids.txt" ]; then
    kill $(cat "$LOG_DIR/pids.txt") 2>/dev/null
    echo "Killed processes from pids.txt"
fi

# Also kill by name (safety net)
pkill -f "flask_api.py"       2>/dev/null
pkill -f "display_server.py"  2>/dev/null
pkill -f "apriltag_handler"   2>/dev/null
pkill -f "sllidar_node"       2>/dev/null
pkill -f "arduino_bridge"     2>/dev/null
pkill -f "slam_toolbox"       2>/dev/null
pkill -f "chromium"           2>/dev/null

echo "Done."
