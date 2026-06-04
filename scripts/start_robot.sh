#!/bin/bash
# ============================================================
# start_robot.sh — Museum Robot Full Startup
# ============================================================
# Starts everything in the correct order:
#   1. ROS bringup (LiDAR + Arduino bridge + SLAM/Nav2)
#   2. Flask API server
#   3. Display web server
#   4. AprilTag ROS handler
#   5. Chromium kiosk display
#
# Usage:
#   ./start_robot.sh          — mapping mode
#   ./start_robot.sh nav      — navigation mode (uses saved map)
# ============================================================

MODE=${1:-mapping}

# Source ROS
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=10

LOG_DIR=~/robot_logs
mkdir -p "$LOG_DIR"

echo "======================================"
echo " Museum Robot Starting — Mode: $MODE"
echo "======================================"

# ── 1. ROS Bringup ───────────────────────────────────────────
echo "[1/5] Starting ROS bringup..."
if [ "$MODE" = "nav" ]; then
    ros2 launch museum_robot navigation.launch.py \
        map:=$HOME/maps/museum_map.yaml \
        > "$LOG_DIR/bringup.log" 2>&1 &
else
    ros2 launch museum_robot bringup.launch.py \
        > "$LOG_DIR/bringup.log" 2>&1 &
fi
BRINGUP_PID=$!
echo "  ROS bringup PID: $BRINGUP_PID"
sleep 5

# ── 2. Flask API ─────────────────────────────────────────────
echo "[2/5] Starting Flask API (port 5000)..."
cd ~/museum_robot_pi
python3 flask_api.py > "$LOG_DIR/flask.log" 2>&1 &
FLASK_PID=$!
echo "  Flask PID: $FLASK_PID"
sleep 2

# ── 3. Display server ────────────────────────────────────────
echo "[3/5] Starting display server (port 8080)..."
python3 web_ui/display_server.py > "$LOG_DIR/display.log" 2>&1 &
DISPLAY_PID=$!
echo "  Display PID: $DISPLAY_PID"
sleep 1

# ── 4. AprilTag handler (nav mode only) ─────────────────────
if [ "$MODE" = "nav" ]; then
    echo "[4/5] Starting AprilTag handler..."
    ros2 run museum_robot apriltag_handler \
        > "$LOG_DIR/apriltag.log" 2>&1 &
    APRIL_PID=$!
    echo "  AprilTag handler PID: $APRIL_PID"
else
    echo "[4/5] Skipping AprilTag handler (mapping mode)"
fi
sleep 1

# ── 5. Chromium kiosk display ────────────────────────────────
echo "[5/5] Starting Chromium kiosk display..."
export DISPLAY=:0
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    http://localhost:8080 \
    > "$LOG_DIR/chromium.log" 2>&1 &
CHROMIUM_PID=$!
echo "  Chromium PID: $CHROMIUM_PID"

echo ""
echo "======================================"
echo " All services started!"
echo " Logs: $LOG_DIR/"
echo "======================================"
echo ""
echo "PIDs saved to $LOG_DIR/pids.txt"
echo "$BRINGUP_PID $FLASK_PID $DISPLAY_PID $CHROMIUM_PID" > "$LOG_DIR/pids.txt"

# Keep script alive so Ctrl+C stops everything
trap 'echo "Shutting down..."; kill $(cat $LOG_DIR/pids.txt) 2>/dev/null; exit' SIGINT SIGTERM
wait
