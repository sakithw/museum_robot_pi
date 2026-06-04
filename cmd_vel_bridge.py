#!/usr/bin/env python3
"""
cmd_vel_bridge.py
Tiny ROS2 node + Flask server on port 5001.
Flask API posts here → publishes /cmd_vel.
Keeps arduino_bridge as the sole serial owner.

Run as systemd service: museum-cmdvel
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from flask import Flask, request, jsonify
import threading, time

app  = Flask(__name__)
_pub = None   # set after ROS init

@app.route('/cmd', methods=['POST'])
def cmd():
    data = request.get_json(silent=True) or {}
    lx   = float(data.get('lx', 0.0))
    az   = float(data.get('az', 0.0))
    if _pub:
        msg = Twist()
        msg.linear.x  = lx
        msg.angular.z = az
        _pub.publish(msg)
    return jsonify({"status": "ok"})

class CmdBridge(Node):
    def __init__(self):
        super().__init__('cmd_vel_bridge')
        global _pub
        _pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info('cmd_vel_bridge ready')

def ros_spin():
    rclpy.init()
    node = CmdBridge()
    rclpy.spin(node)

# Start ROS in background thread
threading.Thread(target=ros_spin, daemon=True).start()
time.sleep(2)  # wait for ROS init

if __name__ == '__main__':
    print("cmd_vel_bridge running on port 5001")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
