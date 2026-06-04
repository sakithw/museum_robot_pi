#!/usr/bin/env python3
"""
udp_listener.py — iPhone AprilTag App UDP Receiver
====================================================
Listens on UDP port 7709 for tag detections from the
iPhone AprilTag app, parses the tag_id, and forwards
to Flask API at localhost:5000/detect.

The app sends a binary packet. Format (from AprilTagReceive.java):
  - 4 bytes: number of tags (int32, big-endian)
  For each tag:
  - 4 bytes: tag id (int32, big-endian)
  - 8 bytes: hamming distance (int64, big-endian)
  - 8*9 bytes: homography matrix (9 x float64, big-endian)

Run: python3 udp_listener.py
"""

import socket
import struct
import requests
import time

UDP_PORT   = 7709
FLASK_URL  = "http://localhost:5000/detect"
COOLDOWN   = 3.0   # seconds between forwarding same tag

last_sent  = {}    # tag_id → timestamp

def parse_packet(data: bytes):
    """Parse the binary UDP packet from the iPhone AprilTag app."""
    try:
        offset = 0
        # Number of detected tags
        num_tags = struct.unpack_from('>i', data, offset)[0]
        offset += 4

        tag_ids = []
        for _ in range(num_tags):
            tag_id   = struct.unpack_from('>i', data, offset)[0];  offset += 4
            hamming  = struct.unpack_from('>q', data, offset)[0];  offset += 8
            # Skip 9 homography doubles (72 bytes)
            offset  += 72
            tag_ids.append(tag_id)

        return tag_ids
    except struct.error:
        return []

def forward_tag(tag_id: int):
    """Send tag detection to Flask API."""
    now = time.time()
    if tag_id in last_sent and now - last_sent[tag_id] < COOLDOWN:
        return   # cooldown — don't spam
    last_sent[tag_id] = now

    try:
        r = requests.post(FLASK_URL,
                          json={"tag_id": tag_id},
                          timeout=1.0)
        print(f"[UDP] Tag {tag_id} → Flask: {r.json().get('status')}")
    except Exception as e:
        print(f"[UDP] Flask forward error: {e}")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    sock.settimeout(1.0)
    print(f"[UDP] Listening on port {UDP_PORT} for AprilTag detections...")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            tag_ids = parse_packet(data)
            for tag_id in tag_ids:
                print(f"[UDP] Received tag {tag_id} from {addr[0]}")
                forward_tag(tag_id)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[UDP] Error: {e}")

if __name__ == '__main__':
    main()
