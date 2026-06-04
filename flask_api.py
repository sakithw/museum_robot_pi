#!/usr/bin/env python3
"""
flask_api.py — Museum Robot HTTP API (clean version)
All drive commands go via /cmd_vel through cmd_vel_bridge (port 5001)
arduino_bridge owns serial exclusively — no conflicts.
"""

from flask import Flask, request, jsonify, render_template_string
import threading, subprocess, time, os

app = Flask(__name__)

from exhibits import EXHIBITS

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

# ── Helper: send cmd_vel via bridge ──────────────────────────────────────────
def send_cmdvel(lx=0.0, az=0.0):
    """POST to cmd_vel_bridge running on port 5001."""
    try:
        import requests
        requests.post('http://localhost:5001/cmd',
                      json={'lx': lx, 'az': az}, timeout=0.3)
    except Exception as e:
        print(f"[Drive] cmd_vel_bridge error: {e}")

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
           f'source ~/ros2_ws/install/setup.bash && '
           f'export ROS_DOMAIN_ID=10 && '
           f'ros2 launch museum_robot {launch} {extra}')
    _ros_process = subprocess.Popen(['bash', '-c', cmd],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
    with _lock:
        _state['ros_running'] = True
    return jsonify({"message": f"Started in {mode} mode"})


@app.route('/stop', methods=['POST'])
def stop_ros():
    global _ros_process
    send_cmdvel(0.0, 0.0)   # stop motors first
    if _ros_process:
        _ros_process.terminate()
        _ros_process = None
    subprocess.Popen(['bash', '-c',
        'sleep 0.5 && '
        'pkill -f async_slam_toolbox_node; '
        'pkill -f sllidar_node; '
        'pkill -f arduino_bridge; '
        'pkill -f scan_filter'])
    with _lock:
        _state['ros_running']  = False
        _state['robot_status'] = 'idle'
    return jsonify({"message": "Stopped"})


@app.route('/save_map', methods=['POST'])
def save_map():
    cmd = ('source /opt/ros/humble/setup.bash && '
           'source ~/ros2_ws/install/setup.bash && '
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
           'source ~/ros2_ws/install/setup.bash && '
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
<title>Museum Tag Scanner</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;min-height:100vh;background:#0a0a14;color:#fff;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:24px 20px;gap:0}
h1{font-size:1.1rem;font-weight:700;letter-spacing:.04em;color:#b0b8ff;
   text-transform:uppercase;margin-bottom:6px}
p.sub{font-size:.8rem;color:#555;margin-bottom:32px}

/* scan button */
#scanBtn{
  width:200px;height:200px;border-radius:50%;
  background:radial-gradient(circle at 40% 35%,#3a3aff,#1a1a6e);
  border:4px solid #4444ff;box-shadow:0 0 40px #3333ff55;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  cursor:pointer;transition:transform .15s,box-shadow .15s;
  -webkit-tap-highlight-color:transparent;user-select:none;position:relative}
#scanBtn:active{transform:scale(.94);box-shadow:0 0 20px #3333ff33}
#scanBtn.scanning{border-color:#00e676;box-shadow:0 0 40px #00e67644;
  animation:pulse 1s ease-in-out infinite}
#scanBtn.hit{border-color:#00e676;background:radial-gradient(circle at 40% 35%,#00c853,#005c24);
  box-shadow:0 0 60px #00e67688;animation:none}
@keyframes pulse{0%,100%{box-shadow:0 0 30px #00e67644}50%{box-shadow:0 0 60px #00e67699}}
#btnIcon{font-size:56px;line-height:1;margin-bottom:6px}
#btnLabel{font-size:.82rem;font-weight:600;color:rgba(255,255,255,.85);letter-spacing:.06em;text-transform:uppercase}
#fileIn{display:none}

/* status */
#result{margin-top:32px;min-height:72px;text-align:center}
#tagname{font-size:1.3rem;font-weight:700;color:#00e676;
  text-shadow:0 0 16px #00e676;letter-spacing:.02em;margin-bottom:6px}
#statusMsg{font-size:.9rem;color:rgba(255,255,255,.6)}

/* spinner ring inside button while uploading */
#ring{position:absolute;inset:-4px;border-radius:50%;
  border:4px solid transparent;border-top-color:#00e676;
  display:none;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
#scanBtn.scanning #ring{display:block}
</style>
</head>
<body>
<h1>Museum Guide</h1>
<p class="sub">Tap to scan an exhibit tag</p>

<div id="scanBtn" onclick="triggerScan()">
  <div id="ring"></div>
  <div id="btnIcon">📷</div>
  <div id="btnLabel">Scan Tag</div>
</div>
<input id="fileIn" type="file" accept="image/*" capture="environment">

<div id="result">
  <div id="tagname"></div>
  <div id="statusMsg">Point your camera at the exhibit's AprilTag</div>
</div>

<script>
const btn       = document.getElementById('scanBtn');
const fileIn    = document.getElementById('fileIn');
const tagnameEl = document.getElementById('tagname');
const statusEl  = document.getElementById('statusMsg');
const btnIcon   = document.getElementById('btnIcon');
const canvas    = document.createElement('canvas');
const ctx       = canvas.getContext('2d');

let busy = false;
let cooldownUntil = 0;

function triggerScan(){
  if(busy || Date.now() < cooldownUntil) return;
  fileIn.click();
}

fileIn.addEventListener('change', ()=>{
  const file = fileIn.files[0];
  fileIn.value = '';
  if(!file || busy) return;
  uploadImage(file);
});

function uploadImage(file){
  busy = true;
  btn.classList.add('scanning');
  btnIcon.textContent = '⏳';
  statusEl.textContent = 'Analysing…';
  tagnameEl.textContent = '';

  // Resize to 800px wide before upload to reduce payload
  const img = new Image();
  img.onload = ()=>{
    const scale = Math.min(1, 800 / img.width);
    canvas.width  = Math.round(img.width  * scale);
    canvas.height = Math.round(img.height * scale);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob=>{
      fetch('/scan_image',{
        method:'POST', body:blob,
        headers:{'Content-Type':'image/jpeg'}
      })
      .then(r=>r.json())
      .then(handleResult)
      .catch(()=>{ setError('Network error — try again'); });
    },'image/jpeg', 0.88);
  };
  img.src = URL.createObjectURL(file);
}

function handleResult(d){
  busy = false;
  btn.classList.remove('scanning');
  btnIcon.textContent = '📷';
  if(d.detected && d.status==='accepted'){
    onHit(d.tag_id, d.exhibit_name);
  } else if(d.detected && d.status==='busy'){
    setInfo('Robot is busy — please wait a moment');
  } else if(d.detected && d.status==='cooldown'){
    setInfo('Just visited — try another exhibit');
  } else if(d.detected && d.status==='not_in_navigation_mode'){
    setInfo('Robot is in mapping mode');
  } else if(d.unknown_tag !== undefined){
    setError('Unknown tag ID: '+d.unknown_tag);
  } else {
    setError('No tag found — try again, closer & steadier');
  }
}

function onHit(tagId, name){
  btn.classList.add('hit');
  btnIcon.textContent = '✓';
  tagnameEl.textContent = name || ('Exhibit '+tagId);
  statusEl.textContent = 'Robot is on its way!';
  cooldownUntil = Date.now() + 14000;
  setTimeout(()=>{
    btn.classList.remove('hit');
    btnIcon.textContent = '📷';
    tagnameEl.textContent = '';
    statusEl.textContent = 'Point your camera at the exhibit\'s AprilTag';
  }, 5000);
}

function setError(msg){ tagnameEl.textContent=''; statusEl.textContent='⚠ '+msg; }
function setInfo(msg) { tagnameEl.textContent=''; statusEl.textContent=msg; }
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
    print("=" * 50)
    print("Museum Robot Flask API — http://0.0.0.0:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
