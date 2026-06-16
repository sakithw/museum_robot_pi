#!/usr/bin/env python3
"""
flask_api.py — Museum Robot HTTP API (clean version)
All drive commands go via /cmd_vel through cmd_vel_bridge (port 5001)
arduino_bridge owns serial exclusively — no conflicts.
"""

from flask import Flask, request, jsonify, render_template_string, render_template
import threading, subprocess, time, os

_web_ui_dir = os.path.join(os.path.dirname(__file__), 'web_ui')
app = Flask(__name__,
            template_folder=os.path.join(_web_ui_dir, 'templates'),
            static_folder=os.path.join(_web_ui_dir, 'static'))

from exhibits import EXHIBITS

@app.route('/')
def index():
    return render_template('index.html')

_state = {
    "pending_tag":    None,
    "current_tag":    None,
    "robot_status":   "idle",
    "language":       "en",
    "mode":           "navigation",
    "ros_running":    False,
    "last_seen_time": 0,
    "cooldown_sec":   15,
    "pos_x":          0.0,
    "pos_y":          0.0,
    "pos_yaw":        0.0,
}
_lock        = threading.Lock()
_ros_process = None
_stop_time   = 0.0

from collections import deque
_log_lines = deque(maxlen=200)
_log_lock  = threading.Lock()

def _stream_process_output(proc):
    """Read stdout+stderr from proc and store in _log_lines."""
    import selectors
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    sel.register(proc.stderr, selectors.EVENT_READ)
    while True:
        events = sel.select(timeout=1.0)
        if not events:
            if proc.poll() is not None:
                break
            continue
        for key, _ in events:
            line = key.fileobj.readline()
            if line:
                text = line.decode('utf-8', errors='replace').rstrip()
                with _log_lock:
                    _log_lines.append(text)
        if proc.poll() is not None:
            break
    sel.close()

# ── Background: poll /odom from ROS ──────────────────────────────────────────
def odom_poller():
    """Read position from file written by odom_relay.py node."""
    import json
    POSITION_FILE = '/tmp/robot_position.json'
    while True:
        try:
            if os.path.exists(POSITION_FILE):
                with open(POSITION_FILE) as f:
                    pos = json.load(f)
                with _lock:
                    _state['pos_x']   = pos.get('x', 0.0)
                    _state['pos_y']   = pos.get('y', 0.0)
                    _state['pos_yaw'] = pos.get('yaw', 0.0)
        except: pass
        time.sleep(0.1)

threading.Thread(target=odom_poller, daemon=True).start()

# ── Background: detect if bringup is actually running ────────────────────────
def ros_watchdog():
    """Poll for arduino_bridge process to sync ros_running with reality."""
    while True:
        alive = bool(subprocess.run(
            ['pgrep', '-f', 'arduino_bridge'],
            capture_output=True).returncode == 0)
        with _lock:
            if time.time() - _stop_time < 5.0:
                _state['ros_running'] = False
            elif _ros_process and _ros_process.poll() is not None:
                _state['ros_running'] = False
            elif alive:
                _state['ros_running'] = True
            else:
                _state['ros_running'] = False
        time.sleep(2)

threading.Thread(target=ros_watchdog, daemon=True).start()

# ── Helper: send cmd_vel via bridge ──────────────────────────────────────────
def send_cmdvel(lx=0.0, az=0.0):
    """POST to cmd_vel_bridge. Try port 5002 (bringup) first, fall back to 5001 (service)."""
    import requests
    for port in [5002, 5001]:
        try:
            requests.post(f'http://localhost:{port}/cmd',
                          json={'lx': lx, 'az': az}, timeout=0.2)
            return
        except Exception:
            continue

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/detect', methods=['POST'])
def detect():
    data = request.get_json(silent=True)
    if not data or 'tag_id' not in data:
        return jsonify({"error": "Missing tag_id"}), 400
    tag_id = int(data['tag_id'])
    if tag_id not in EXHIBITS:
        return jsonify({"error": f"Unknown tag_id {tag_id}"}), 404
    with _lock:
        if _state['mode'] != 'navigation':
            return jsonify({"status": "ignored"}), 200
        now = time.time()
        if (tag_id == _state['current_tag'] and
                now - _state['last_seen_time'] < _state['cooldown_sec']):
            return jsonify({"status": "cooldown"}), 200
        if _state['robot_status'] in ('navigating', 'speaking'):
            return jsonify({"status": "busy"}), 200
        _state.update(pending_tag=tag_id, current_tag=tag_id,
                      last_seen_time=now, robot_status='navigating')
        lang = _state['language']
    print(f"[API] Tag {tag_id} detected")
    return jsonify({"status": "accepted", "tag_id": tag_id,
                    "exhibit": EXHIBITS[tag_id]['name'][lang]})


@app.route('/status')
def status():
    with _lock:
        s = dict(_state)
    exhibit = None
    if s['current_tag'] and s['current_tag'] in EXHIBITS and s['mode'] == 'navigation':
        lang = s['language']
        ex   = EXHIBITS[s['current_tag']]
        exhibit = {"tag_id":      s['current_tag'],
                   "name":        ex['name'][lang],
                   "description": ex['description'][lang]}
    return jsonify({"robot_status": s['robot_status'],
                    "exhibit":      exhibit,
                    "mode":         s['mode'],
                    "ros_running":  s['ros_running'],
                    "position":     {"x": s['pos_x'],
                                     "y": s['pos_y'],
                                     "yaw": s['pos_yaw']}})


@app.route('/poll')
def poll():
    with _lock:
        tag_id = _state['pending_tag']
        lang   = _state['language']
        _state['pending_tag'] = None
    if tag_id is None:
        return jsonify({"tag_id": None})
    return jsonify({"tag_id": tag_id,
                    "nav_goal": EXHIBITS[tag_id]['nav_goal'],
                    "language": lang})


@app.route('/set_status', methods=['POST'])
def set_status():
    data = request.get_json(silent=True) or {}
    with _lock:
        if 'robot_status' in data:
            _state['robot_status'] = data['robot_status']
    return jsonify({"status": "ok"})


@app.route('/language', methods=['POST'])
def set_language():
    data = request.get_json(silent=True) or {}
    lang = data.get('lang', 'en')
    if lang not in ('en', 'si', 'ta'):
        return jsonify({"error": "Invalid"}), 400
    with _lock:
        _state['language'] = lang
    return jsonify({"status": "ok"})


@app.route('/mode', methods=['POST'])
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'navigation')
    if mode not in ('navigation', 'mapping'):
        return jsonify({"error": "Invalid"}), 400
    with _lock:
        _state['mode'] = mode
        if mode == 'mapping':
            _state['current_tag']  = None
            _state['robot_status'] = 'idle'
    print(f"[API] Mode: {mode}")
    return jsonify({"status": "ok"})


@app.route('/start', methods=['POST'])
def start_ros():
    global _ros_process
    with _lock:
        mode = _state['mode']
    if _ros_process and _ros_process.poll() is None:
        return jsonify({"message": "Already running"})
    launch = 'bringup.launch.py' if mode == 'mapping' else 'navigation.launch.py'
    extra  = f'map:={os.path.expanduser("~/maps/museum_map.yaml")}' \
             if mode == 'navigation' else ''
    cmd = (f'source /opt/ros/humble/setup.bash && '
           f'source ~/new_ros2/install/setup.bash && '
           f'export ROS_DOMAIN_ID=10 && '
           f'ros2 launch museum_robot {launch} {extra}')
    with _log_lock:
        _log_lines.clear()
        _log_lines.append(f'[webapp] Starting {launch}...')
    _ros_process = subprocess.Popen(
        ['bash', '-c', cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    threading.Thread(target=_stream_process_output,
                     args=(_ros_process,), daemon=True).start()
    with _lock:
        _state['ros_running'] = True
    return jsonify({"message": f"Started in {mode} mode"})


@app.route('/stop', methods=['POST'])
def stop_ros():
    global _ros_process, _stop_time
    send_cmdvel(0.0, 0.0)
    _ros_process = None
    subprocess.run(['bash', '-c',
        'pkill -9 -f "ros2 launch"; '
        'pkill -9 -f arduino_bridge; '
        'pkill -9 -f sllidar_node; '
        'pkill -9 -f async_slam_toolbox_node; '
        'pkill -9 -f scan_filter; '
        'pkill -9 -f bt_navigator; '
        'pkill -9 -f controller_server; '
        'pkill -9 -f planner_server; '
        'pkill -9 -f amcl; '
        'pkill -9 -f map_server'])
    with _lock:
        _state['ros_running'] = False
        _state['robot_status'] = 'idle'
    _stop_time = time.time()
    return jsonify({"message": "Stopped"})


@app.route('/launch_log')
def launch_log():
    with _log_lock:
        lines = list(_log_lines)[-100:]
    return jsonify({"lines": lines})


@app.route('/save_map', methods=['POST'])
def save_map():
    cmd = ('source /opt/ros/humble/setup.bash && '
           'source ~/new_ros2/install/setup.bash && '
           'export ROS_DOMAIN_ID=10 && mkdir -p ~/maps && '
           'ros2 service call /slam_toolbox/serialize_map '
           'slam_toolbox/srv/SerializePoseGraph '
           '"filename: \'/home/pi/maps/museum_map\'" && '
           'ros2 run nav2_map_server map_saver_cli '
           '-f ~/maps/museum_map -t /map '
           '--ros-args -p save_map_timeout:=10.0')
    subprocess.Popen(['bash', '-c', cmd])
    return jsonify({"message": "Saving… check ~/maps/ shortly"})


_MAPPING_MAX_LX = 0.15   # m/s max during manual mapping (slow and careful)
_MAPPING_MAX_AZ = 0.40   # rad/s max during manual mapping
_NAV_MAX_LX     = 0.25   # m/s max during manual driving in navigation mode
_NAV_MAX_AZ     = 0.50   # rad/s max during navigation mode

@app.route('/drive', methods=['POST'])
def drive():
    """Receive Twist from web UI, forward to cmd_vel_bridge.
    speed (0-1) is fraction of mode-appropriate max velocity,
    so the robot never exceeds safe speeds regardless of slider position.
    """
    data = request.get_json(silent=True) or {}
    lx   = float(data.get('linear',  {}).get('x', 0.0))   # ±1 direction
    az   = float(data.get('angular', {}).get('z', 0.0))   # ±1 direction
    spd  = float(data.get('speed', 0.5))                   # 0.0–1.0 fraction
    with _lock:
        mode = _state['mode']
    max_lx = _MAPPING_MAX_LX if mode == 'mapping' else _NAV_MAX_LX
    max_az = _MAPPING_MAX_AZ if mode == 'mapping' else _NAV_MAX_AZ
    send_cmdvel(lx * spd * max_lx, az * spd * max_az)
    return jsonify({"status": "ok"})


@app.route('/mark_goal/<int:tag_id>', methods=['POST'])
def mark_goal(tag_id):
    with _lock:
        x   = _state['pos_x']
        y   = _state['pos_y']
        yaw = _state['pos_yaw']
    if tag_id not in EXHIBITS:
        return jsonify({"error": "Unknown tag"}), 404
    EXHIBITS[tag_id]['nav_goal'] = {'x': x, 'y': y, 'yaw': yaw}
    _save_nav_goals()
    print(f"[API] Nav goal saved: tag={tag_id} x={x} y={y} yaw={yaw}")
    return jsonify({"status": "saved", "tag_id": tag_id,
                    "nav_goal": {"x": x, "y": y, "yaw": yaw}})


def _save_nav_goals():
    """Write only the nav_goals section to a separate file."""
    goals = {tid: ex['nav_goal'] for tid, ex in EXHIBITS.items()}
    path  = os.path.join(os.path.dirname(__file__), 'nav_goals.py')
    with open(path, 'w') as f:
        f.write('# Auto-saved nav goals — do not edit manually\n')
        f.write(f'NAV_GOALS = {goals!r}\n')
    print(f"[API] nav_goals.py updated")


@app.route('/optimize_map', methods=['POST'])
def optimize_map():
    """Trigger slam_toolbox pose graph optimization to improve map quality."""
    cmd = ('source /opt/ros/humble/setup.bash && '
           'source ~/new_ros2/install/setup.bash && '
           'export ROS_DOMAIN_ID=10 && '
           'ros2 service call /slam_toolbox/optimize_poses '
           'slam_toolbox/srv/TriggerService')
    subprocess.Popen(['bash', '-c', cmd])
    return jsonify({"message": "Optimizing pose graph… wait 5 s then save map"})


@app.route('/exhibit/<int:tag_id>')
def get_exhibit(tag_id):
    if tag_id not in EXHIBITS:
        return jsonify({"error": "Not found"}), 404
    return jsonify(EXHIBITS[tag_id])


# ── AprilTag image scanner (iPhone web UI) ────────────────────────────────────
_apriltag_detector = None
_apriltag_det_lock = threading.Lock()

def _get_apriltag_detector():
    global _apriltag_detector
    if _apriltag_detector is None:
        from pupil_apriltags import Detector
        _apriltag_detector = Detector(families='tag36h11', nthreads=1)
    return _apriltag_detector

_SCANNER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta charset="UTF-8">
<title>Museum Scanner</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#000;overflow:hidden;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#fff}
#video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
#overlay{position:absolute;inset:0;pointer-events:none;
  display:flex;flex-direction:column;align-items:center;justify-content:center}
#box{width:220px;height:220px;border:3px solid rgba(255,255,255,.4);border-radius:20px;
  position:relative;transition:border-color .25s,box-shadow .25s}
#box.hit{border-color:#00e676;box-shadow:0 0 40px #00e67688}
#scanline{position:absolute;left:8px;right:8px;height:2px;
  background:linear-gradient(90deg,transparent,#00e676,transparent);
  top:0;animation:sweep 1.8s ease-in-out infinite}
@keyframes sweep{0%{top:4px;opacity:1}100%{top:calc(100% - 6px);opacity:.3}}
#box.hit #scanline{display:none}
#tick{position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;font-size:64px;opacity:0;transition:opacity .2s}
#box.hit #tick{opacity:1}
#topbar{position:absolute;top:0;left:0;right:0;padding:14px 16px 20px;
  background:linear-gradient(180deg,rgba(0,0,0,.7),transparent);
  font-size:.9rem;font-weight:600;text-align:center;letter-spacing:.03em}
#label{position:absolute;bottom:110px;left:0;right:0;text-align:center;
  font-size:1.2rem;font-weight:700;color:#00e676;
  text-shadow:0 0 14px #00e676;min-height:1.5em}
#status{position:absolute;bottom:52px;left:0;right:0;text-align:center;
  font-size:.85rem;color:rgba(255,255,255,.65);text-shadow:0 1px 4px #000}
#dot{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:#555;margin-right:6px;vertical-align:middle;transition:background .3s}
#dot.active{background:#00e676;box-shadow:0 0 6px #00e676}
</style>
</head>
<body>
<video id="video" autoplay playsinline muted></video>
<canvas id="canvas" style="display:none"></canvas>
<div id="overlay">
  <div id="box"><div id="scanline"></div><div id="tick">✓</div></div>
</div>
<div id="topbar">Museum Guide — Auto Scanner</div>
<div id="label"></div>
<div id="status"><span id="dot"></span><span id="statusTxt">Starting camera…</span></div>

<script>
const video  = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx    = canvas.getContext('2d');
const box    = document.getElementById('box');
const label  = document.getElementById('label');
const dot    = document.getElementById('dot');
const stxt   = document.getElementById('statusTxt');

canvas.width = 640; canvas.height = 480;

let busy = false, cooldownUntil = 0;

function setStatus(msg, live){ stxt.textContent=msg; dot.className=live?'active':''; }

navigator.mediaDevices.getUserMedia({
  video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}}
}).then(stream=>{
  video.srcObject = stream;
  video.addEventListener('loadedmetadata', ()=>{
    setStatus('Scanning…', true);
    setInterval(doScan, 700);
  });
}).catch(err=>{
  setStatus('Camera error: '+err.message, false);
});

function doScan(){
  if(busy || Date.now() < cooldownUntil) return;
  busy = true;
  ctx.drawImage(video, 0, 0, 640, 480);
  canvas.toBlob(blob=>{
    if(!blob){ busy=false; return; }
    fetch('/scan_image',{method:'POST',body:blob,
      headers:{'Content-Type':'image/jpeg'}})
    .then(r=>r.json())
    .then(d=>{
      busy = false;
      if(d.detected && d.status==='accepted'){
        onHit(d.tag_id, d.exhibit_name);
      } else if(d.detected && d.status==='busy'){
        setStatus('Robot busy — waiting…', true);
      } else if(d.detected && d.status==='cooldown'){
        setStatus('Scanning…', true);
      }
    })
    .catch(()=>{ busy=false; });
  },'image/jpeg',0.82);
}

function onHit(tagId, name){
  box.classList.add('hit');
  label.textContent = name||('Exhibit '+tagId);
  setStatus('On the way!', true);
  cooldownUntil = Date.now() + 14000;
  setTimeout(()=>{
    box.classList.remove('hit');
    label.textContent = '';
    setStatus('Scanning…', true);
  }, 4000);
}
</script>
</body>
</html>"""


@app.route('/scanner')
def scanner():
    return render_template_string(_SCANNER_HTML)


@app.route('/scan_image', methods=['POST'])
def scan_image():
    import numpy as np
    import cv2

    data = request.get_data()
    if not data:
        return jsonify({'detected': False})

    nparr = np.frombuffer(data, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return jsonify({'detected': False})

    with _apriltag_det_lock:
        detections = _get_apriltag_detector().detect(img)

    if not detections:
        return jsonify({'detected': False})

    best   = max(detections, key=lambda d: d.decision_margin)
    tag_id = int(best.tag_id)

    if tag_id not in EXHIBITS:
        return jsonify({'detected': False, 'unknown_tag': tag_id})

    with _lock:
        lang = _state['language']
        if _state['mode'] != 'navigation':
            return jsonify({'detected': True, 'tag_id': tag_id, 'status': 'not_in_navigation_mode'})
        now = time.time()
        if (tag_id == _state['current_tag'] and
                now - _state['last_seen_time'] < _state['cooldown_sec']):
            return jsonify({'detected': True, 'tag_id': tag_id, 'status': 'cooldown',
                            'exhibit_name': EXHIBITS[tag_id]['name'][lang]})
        if _state['robot_status'] in ('navigating', 'speaking'):
            return jsonify({'detected': True, 'tag_id': tag_id, 'status': 'busy',
                            'exhibit_name': EXHIBITS[tag_id]['name'][lang]})
        _state.update(pending_tag=tag_id, current_tag=tag_id,
                      last_seen_time=now, robot_status='navigating')

    exhibit_name = EXHIBITS[tag_id]['name'][lang]
    print(f"[Scanner] Tag {tag_id} → {exhibit_name}")
    return jsonify({'detected': True, 'tag_id': tag_id,
                    'exhibit_name': exhibit_name, 'status': 'accepted'})


if __name__ == '__main__':
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _cert = _os.path.join(_base, 'cert.pem')
    _key  = _os.path.join(_base, 'key.pem')
    _ssl  = (_cert, _key) if _os.path.exists(_cert) else None
    _proto = 'https' if _ssl else 'http'
    print("=" * 50)
    print(f"Museum Robot Flask API — {_proto}://0.0.0.0:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True,
            ssl_context=_ssl)
