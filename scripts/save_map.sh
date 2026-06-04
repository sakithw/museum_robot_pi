#!/bin/bash
# ============================================================
# save_map.sh — Save current SLAM map
# ============================================================
# Usage: ./save_map.sh [optional_map_name]
# Default name: museum_map
# ============================================================

source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=10

MAP_NAME=${1:-museum_map}
MAP_PATH="$HOME/maps/$MAP_NAME"
mkdir -p ~/maps

echo "Saving map to: $MAP_PATH"

# Save pose graph (for re-loading into SLAM)
ros2 service call /slam_toolbox/serialize_map \
    slam_toolbox/srv/SerializePoseGraph \
    "filename: '$MAP_PATH'"

# Save PGM + YAML (for Nav2)
ros2 run nav2_map_server map_saver_cli \
    -f "$MAP_PATH" \
    -t /map \
    --ros-args -p save_map_timeout:=10.0

echo ""
echo "Saved files:"
ls -lh ~/maps/${MAP_NAME}*
