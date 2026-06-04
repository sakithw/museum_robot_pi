#!/usr/bin/env python3
"""
odom_relay.py — writes robot position (MAP frame) to /tmp/robot_position.json

Uses TF to look up map→base_link so the recorded coordinates are in the
map frame regardless of whether slam_toolbox (mapping) or AMCL (navigation)
is providing the map→odom transform.  Flask reads this file for mark_goal.

Run as systemd service: museum-odom
"""
import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener
import math
import json

POSITION_FILE = '/tmp/robot_position.json'


class OdomRelay(Node):

    def __init__(self):
        super().__init__('odom_relay')
        self._tf_buffer   = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        # Poll TF at 10 Hz
        self.create_timer(0.1, self._update)
        self.get_logger().info('odom_relay ready (map frame via TF)')

    def _update(self):
        try:
            t = self._tf_buffer.lookup_transform(
                'map', 'base_link',
                rclpy.time.Time(),          # latest available
                timeout=rclpy.duration.Duration(seconds=0.05))
        except Exception:
            return  # TF not yet available — keep old file

        x = t.transform.translation.x
        y = t.transform.translation.y
        q = t.transform.rotation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))

        try:
            with open(POSITION_FILE, 'w') as f:
                json.dump({'x': round(x, 3),
                           'y': round(y, 3),
                           'yaw': round(yaw, 4)}, f)  # radians
        except Exception:
            pass


def main():
    rclpy.init()
    node = OdomRelay()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
