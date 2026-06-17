// app.js — Museum Guide Robot Web UI

let currentLang = 'en';
let currentMode = 'navigation';
let driveInterval = null;

const exhibitNames = {
  1:'Ancient Pottery', 2:'Royal Regalia', 3:'Ancient Weapons',
  4:'Traditional Textiles', 5:'Ancient Coins'
};

const msgs = {
  en:{ idle:'Approach an exhibit to begin', navigating:'On the way…', speaking:'Describing…',
       nav:'Navigating to exhibit…', speak:'Describing exhibit…' },
  si:{ idle:'ප්‍රදර්ශනයකට ළඟා වන්න', navigating:'එන්නම් ඉන්න…', speaking:'විස්තර කරමින්…',
       nav:'ප්‍රදර්ශනයට යමින්…', speak:'විස්තර කරමින්…' },
  ta:{ idle:'கண்காட்சியை அணுகவும்', navigating:'வருகிறேன்…', speaking:'விவரிக்கிறேன்…',
       nav:'கண்காட்சிக்கு செல்கிறேன்…', speak:'விவரிக்கிறேன்…' },
};

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, color='#6c63ff'){
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.borderColor = color;
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}

// ── Tabs ───────────────────────────────────────────────────────────────────
function switchTab(tab, el){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('panelExhibit').classList.toggle('active', tab==='exhibit');
  document.getElementById('panelRemote').classList.toggle('active',  tab==='remote');
  document.getElementById('panelGoals').classList.toggle('active',   tab==='goals');
  document.getElementById('panelTerminal').classList.toggle('active', tab==='terminal');
  if(tab==='goals') renderGoals();
}

// ── Language ───────────────────────────────────────────────────────────────
function setLang(lang, btn){
  currentLang = lang;
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  fetch('/language',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({lang})});
}

// ── Mode ───────────────────────────────────────────────────────────────────
// Speed scaling is enforced server-side in flask_api.py:
//   mapping → max 0.15 m/s travel, 0.40 rad/s turn
//   navigation → max 0.25 m/s travel, 0.50 rad/s turn
// Slider percentage is fraction of those mode maximums.
function setMode(mode){
  currentMode = mode;
  document.getElementById('sysMode').textContent = mode==='mapping'?'Map':'Nav';
  const noteEl = document.getElementById('speedNoteVal');
  if(mode==='mapping'){
    if(noteEl) noteEl.textContent = '0.15 m/s (mapping)';
    document.getElementById('idleScreen').style.display='none';
    document.getElementById('mappingScreen').classList.add('visible');
    document.getElementById('exhibitCard').classList.remove('visible');
  } else {
    if(noteEl) noteEl.textContent = '0.25 m/s (nav)';
    document.getElementById('mappingScreen').classList.remove('visible');
    document.getElementById('idleScreen').style.display='flex';
  }
  fetch('/mode',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
  document.getElementById('btnNavMode').classList.toggle('mode-active', mode==='navigation');
  document.getElementById('btnMapMode').classList.toggle('mode-active', mode==='mapping');
}

// ── Robot controls ─────────────────────────────────────────────────────────
async function startRobot(){
  toast('Starting…','#10b981');
  const r = await fetch('/start',{method:'POST'});
  const d = await r.json();
  toast(d.message||'Started','#10b981');
}
async function stopRobot(){
  toast('Stopping…','#ef4444');
  await fetch('/stop',{method:'POST'});
  stopDrive();
  toast('Stopped','#ef4444');
}
async function saveMap(){
  toast('Saving map…','#6c63ff');
  const r = await fetch('/save_map',{method:'POST'});
  const d = await r.json();
  toast(d.message||'Saved!','#10b981');
}
async function optimizeMap(){
  toast('Optimizing pose graph…','#f59e0b');
  const r = await fetch('/optimize_map',{method:'POST'});
  const d = await r.json();
  toast(d.message||'Done!','#10b981');
}

// ── Drive ──────────────────────────────────────────────────────────────────
// Travel speed: 0–50% of max (slider 1)
// Turn speed:   0–100% of max (slider 2)
// ✅ FIX: L/R angular signs corrected (positive az = turn left in ROS)

function getTravelSpeed(){ return parseInt(document.getElementById('travelSlider').value)/100; }
function getTurnSpeed(){   return parseInt(document.getElementById('turnSlider').value)/100; }

const dirMap = {
  F:{ lx: 1, az: 0,  label:'⬆️ FORWARD',  useTurn:false },
  B:{ lx:-1, az: 0,  label:'⬇️ BACKWARD', useTurn:false },
  L:{ lx: 0, az: 1,  label:'⬅️ LEFT',     useTurn:true  }, // ✅ positive az = left in ROS
  R:{ lx: 0, az:-1,  label:'➡️ RIGHT',    useTurn:true  }, // ✅ negative az = right in ROS
};

function sendDriveCmd(lx, az, useTurn){
  const spd = useTurn ? getTurnSpeed() : getTravelSpeed();
  fetch('/drive',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      linear: {x: lx, y:0, z:0},
      angular:{x:0,   y:0, z:az},
      speed: spd
    })
  }).catch(()=>{});
}

function startDrive(dir){
  if(driveInterval) return;
  const d = dirMap[dir];
  document.getElementById('driveStatus').textContent = d.label;
  document.getElementById('driveStatus').classList.add('moving');
  sendDriveCmd(d.lx, d.az, d.useTurn);
  driveInterval = setInterval(()=>sendDriveCmd(d.lx, d.az, d.useTurn), 100);
}

function stopDrive(){
  if(driveInterval){ clearInterval(driveInterval); driveInterval=null; }
  sendDriveCmd(0, 0, false);
  document.getElementById('driveStatus').textContent = '🛑 STOPPED';
  document.getElementById('driveStatus').classList.remove('moving');
}

// Keyboard
const keyDirMap = {ArrowUp:'F', ArrowDown:'B', ArrowLeft:'L', ArrowRight:'R'};
document.addEventListener('keydown', e=>{
  const dir = keyDirMap[e.key];
  if(dir && !driveInterval) startDrive(dir);
  if(e.key===' '){ e.preventDefault(); stopDrive(); }
});
document.addEventListener('keyup', e=>{
  if(keyDirMap[e.key]) stopDrive();
});

// ── Nav Goals ──────────────────────────────────────────────────────────────
let savedGoals = {};

function renderGoals(){
  const list = document.getElementById('goalsList');
  list.innerHTML = '';
  for(let i=1;i<=5;i++){
    const g = savedGoals[i];
    const coords = g
      ? `x: ${g.x.toFixed(3)}  y: ${g.y.toFixed(3)}  yaw: ${g.yaw.toFixed(1)}°`
      : 'Not set — drive here and click Mark';
    list.innerHTML += `
      <div class="goal-card">
        <div style="flex:1">
          <div class="goal-name">Exhibit ${i} — ${exhibitNames[i]||'Exhibit'}</div>
          <div class="goal-coords ${g?'set':''}" id="coords${i}">${coords}</div>
        </div>
        <button class="mark-btn ${g?'saved':''}" onclick="markGoal(${i})">
          ${g ? '✅ Update' : '📍 Mark Here'}
        </button>
      </div>`;
  }
}

async function markGoal(tagId){
  toast(`Marking exhibit ${tagId}…`,'#6c63ff');
  try{
    const r = await fetch(`/mark_goal/${tagId}`,{method:'POST'});
    const d = await r.json();
    if(d.status==='saved'){
      savedGoals[tagId] = d.nav_goal;
      renderGoals();
      toast(`✅ Exhibit ${tagId} saved!  x:${d.nav_goal.x.toFixed(2)} y:${d.nav_goal.y.toFixed(2)}`,'#10b981');
    } else {
      toast('Error: '+JSON.stringify(d),'#ef4444');
    }
  } catch(e){ toast('Network error','#ef4444'); }
}

// ── Status Poll ────────────────────────────────────────────────────────────
async function pollStatus(){
  try{
    const data   = await (await fetch('/status')).json();
    const status = data.robot_status;
    const exhibit= data.exhibit;
    const pos    = data.position || {};
    const m      = msgs[currentLang] || msgs.en;

    // Position
    document.getElementById('posX').textContent   = (pos.x||0).toFixed(3);
    document.getElementById('posY').textContent   = (pos.y||0).toFixed(3);
    document.getElementById('posYaw').textContent = (pos.yaw||0).toFixed(1);

    // Status
    const dot = driveInterval ? 'driving' : status;
    document.getElementById('statusDot').className   = 'status-dot '+dot;
    document.getElementById('statusText').textContent = driveInterval ? '🕹️ Driving' : (m[status]||status);
    document.getElementById('sysStatus').textContent  = status.charAt(0).toUpperCase()+status.slice(1);
    document.getElementById('sysRos').textContent     = data.ros_running ? '✅ Running' : '❌ Stopped';

    if(currentMode==='mapping') return;

    if(!exhibit || status==='idle'){
      document.getElementById('idleScreen').style.display='flex';
      document.getElementById('exhibitCard').classList.remove('visible');
      document.getElementById('idleText').textContent = m.idle;
      return;
    }

    document.getElementById('idleScreen').style.display='none';
    document.getElementById('exhibitCard').classList.add('visible');
    document.getElementById('exhibitTag').textContent  = 'EXHIBIT '+exhibit.tag_id;
    document.getElementById('exhibitName').textContent = exhibit.name;
    document.getElementById('exhibitDesc').textContent = exhibit.description;
    document.getElementById('navIndicator').classList.toggle('visible', status==='navigating');
    document.getElementById('speakIndicator').classList.toggle('visible', status==='speaking');
    document.getElementById('navText').textContent   = m.nav;
    document.getElementById('speakText').textContent = m.speak;
  } catch(e){}
}

setInterval(pollStatus, 1000);
pollStatus();
setMode('navigation');
renderGoals();

// ── Launch Log ─────────────────────────────────────────────────────
let logVisible = false;
let lastLogCount = 0;

function toggleLog(){
  logVisible = !logVisible;
  document.getElementById('logPanel').style.display = logVisible ? 'flex' : 'none';
  document.getElementById('logToggleBtn').textContent = logVisible ? '✕ Hide Log' : '📡 Show Log';
}

async function pollLog(){
  if(!logVisible) return;
  try{
    const data = await (await fetch('/launch_log')).json();
    const lines = data.lines || [];
    if(lines.length !== lastLogCount){
      lastLogCount = lines.length;
      const el = document.getElementById('logOutput');
      el.textContent = lines.join('\n');
      el.scrollTop = el.scrollHeight;
    }
  } catch(e){}
}

setInterval(pollLog, 2000);

// ── Terminal Tab ───────────────────────────────────────────────────────────
async function launchBringupInTerminal(){
  const out = document.getElementById('terminalOutput');
  out.textContent += '\n$ Setting mode to mapping and starting bringup...\n';
  out.scrollTop = out.scrollHeight;
  try{
    await fetch('/mode', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mode:'mapping'})
    });
    const r = await fetch('/start', {method:'POST'});
    const d = await r.json();
    out.textContent += (d.message || 'started') + ' - check Show Log panel for live output\n';
  } catch(e){
    out.textContent += 'Error: ' + e.message + '\n';
  }
  out.scrollTop = out.scrollHeight;
}

async function launchNavInTerminal(){
  const out = document.getElementById('terminalOutput');
  out.textContent += '\n$ Setting mode to navigation and starting...\n';
  out.scrollTop = out.scrollHeight;
  try{
    await fetch('/mode', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mode:'navigation'})
    });
    const r = await fetch('/start', {method:'POST'});
    const d = await r.json();
    out.textContent += (d.message || 'started') + ' - check Show Log panel for live output\n';
  } catch(e){
    out.textContent += 'Error: ' + e.message + '\n';
  }
  out.scrollTop = out.scrollHeight;
}

async function stopGracefulInTerminal(){
  const out = document.getElementById('terminalOutput');
  out.textContent += '\n$ Sending Ctrl+C (SIGINT) to stop gracefully...\n';
  out.scrollTop = out.scrollHeight;
  try{
    const r = await fetch('/stop_graceful', {method:'POST'});
    const d = await r.json();
    out.textContent += (d.message || 'stopped') + '\n';
  } catch(e){
    out.textContent += 'Error: ' + e.message + '\n';
  }
  out.scrollTop = out.scrollHeight;
}

async function quickCmd(cmd){ await runCmd(cmd); }
async function runTypedCmd(){
  const input = document.getElementById('cmdInput');
  const cmd = input.value.trim();
  if(!cmd) return;
  await runCmd(cmd);
  input.value = '';
}
async function runCmd(cmd){
  const out = document.getElementById('terminalOutput');
  out.textContent += '\n$ ' + cmd + '\n';
  out.scrollTop = out.scrollHeight;
  try{
    const r = await fetch('/run_command', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({cmd: cmd})
    });
    const d = await r.json();
    out.textContent += (d.output || d.error || '(no output)') + '\n';
    out.scrollTop = out.scrollHeight;
  } catch(e){
    out.textContent += 'Error: ' + e.message + '\n';
  }
}
