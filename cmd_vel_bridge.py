#!/usr/bin/env python3
"""
cmd_vel_bridge.py
ROS2 node + Flask server.
Flask API posts here → publishes /cmd_vel.

Port is controlled by CMD_VEL_BRIDGE_PORT env var (default 5001).
When launched from bringup.launch.py it runs on port 5002 so it
shares the same DDS context as arduino_bridge.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from flask import Flask, request, jsonify
import threading, time, os

PORT = int(os.environ.get('CMD_VEL_BRIDGE_PORT', 5001))

app  = Flask(__name__)
_pub = None
_pub_lock = threading.Lock()

@app.route('/cmd', methods=['POST'])
def cmd():
    data = request.get_json(silent=True) or {}
    lx   = float(data.get('lx', 0.0))
    az   = float(data.get('az', 0.0))
    with _pub_lock:
        pub = _pub
    if pub:
        try:
            msg = Twist()
            msg.linear.x  = lx
            msg.angular.z = az
            pub.publish(msg)
        except Exception as e:
            print(f'[ROS] publish error: {e}')
    return jsonify({"status": "ok"})

def ros_spin():
    global _pub
    while True:
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        try:
            rclpy.init()
            node = Node('cmd_vel_bridge')
            with _pub_lock:
                _pub = node.create_publisher(Twist, '/cmd_vel', 10)
            node.get_logger().info(f'cmd_vel_bridge ready (port {PORT})')
            rclpy.spin(node)
        except Exception as e:
            print(f'[ROS] spin error: {e}')
        finally:
            with _pub_lock:
                _pub = None
            try:
                rclpy.shutdown()
            except Exception:
                pass
        time.sleep(3)

threading.Thread(target=ros_spin, daemon=True).start()
time.sleep(3)

if __name__ == '__main__':
    print(f"cmd_vel_bridge running on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
