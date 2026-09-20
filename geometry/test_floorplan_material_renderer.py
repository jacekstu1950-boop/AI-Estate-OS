import json
import math
from pathlib import Path


def _camera_angles(position, target):
    dx = target[0] - position[0]
    dy = target[1] - position[1]
    dz = target[2] - position[2]
    yaw = math.atan2(dy, dx)
    horizontal = math.hypot(dx, dy)
    pitch = math.atan2(dz, horizontal)
    return yaw, pitch


def build_html(scene):
    if scene.get("source_rights_status") != "OWN_TEST_ASSET":
        raise ValueError("Renderer materiałów działa wyłącznie dla OWN_TEST_ASSET.")
    if scene.get("geometry_validation", {}).get("status") != "PASS":
        raise ValueError("Scena 3D nie przeszła walidacji geometrii.")

    cameras = scene.get("camera_presets", {})
    visual = scene.get("visualization_preset")
    required_presets = ["overview_full_apartment", "interior_living"]
    for preset_name in required_presets:
        if preset_name not in cameras:
            raise ValueError(f"Brak presetu kamery: {preset_name}")
    if not visual or visual.get("status") != "TEST_STAGING":
        raise ValueError("Brak poprawnego presetu TEST_STAGING.")

    camera_payloads = {}
    for preset_name, camera in cameras.items():
        yaw, pitch = _camera_angles(camera["position_m"], camera["target_m"])
        camera_payloads[preset_name] = {
            **camera,
            "yaw": yaw,
            "pitch": pitch,
        }

    render_scene = {
        **scene,
        "objects": scene.get("objects", []) + visual.get("staging_objects", []),
    }

    payload = {
        "scene": render_scene,
        "cameras": camera_payloads,
        "default_preset": "overview_full_apartment",
        "visual": visual,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    template = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Estate-OS — testowa wizualizacja materiałowa</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:Arial,sans-serif; background:#e9edf2; color:#1f2937; }
  header { background:#111827; color:white; padding:18px 22px; }
  header h1 { margin:0 0 5px; font-size:22px; }
  main { max-width:1180px; margin:0 auto; padding:20px; }
  .card { background:white; border-radius:14px; padding:16px; box-shadow:0 4px 18px rgba(0,0,0,.10); }
  .toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  button { border:1px solid #d1d5db; background:#111827; color:white; border-radius:8px; padding:9px 12px; font-weight:700; cursor:pointer; }
  .status { margin-left:auto; color:#047857; font-weight:700; }
  .muted { color:#6b7280; }
  .legend { display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; font-size:13px; color:#4b5563; }
  #viewport { width:100%; height:650px; display:block; border:1px solid #cbd5e1; border-radius:12px; cursor:grab; background:#dfe7ef; }
  #viewport:active { cursor:grabbing; }
</style>
</head>
<body>
<header>
  <h1>AI-Estate-OS — Etap 5E: materiały i światło</h1>
  <div>Własny rzut testowy · 35 mm · aranżacja demonstracyjna</div>
</header>
<main>
  <div class="card">
    <div class="toolbar">
      <button id="presetOverview" type="button">Całe mieszkanie</button>
      <button id="presetLiving" type="button">Wnętrze salonu</button>
      <button id="reset" type="button">Reset bieżącego widoku</button>
      <button id="toggleStaging" type="button">Meble testowe</button>
      <button id="toggleGuides" type="button">Linie pomocnicze</button>
      <span class="muted">Domyślnie otwiera się całe mieszkanie. Rolka zmienia zoom.</span>
      <span class="status">OWN_TEST_ASSET · TEST_STAGING · PASS</span>
    </div>
    <canvas id="viewport"></canvas>
    <div class="legend">
      <span>Ściany: ciepła biel</span>
      <span>Podłoga: jasny dąb</span>
      <span>Sofa: oliwkowa</span>
      <span>Fotel: terakota</span>
      <span>Dywan: piaskowy</span>
      <span>Światło: ambient + okno</span>
    </div>
  </div>
</main>
<script>
const payload = __PAYLOAD_JSON__;
const scene = payload.scene;
const cameras = payload.cameras;
const visual = payload.visual;
const canvas = document.getElementById('viewport');
const ctx = canvas.getContext('2d');

let activePresetName = payload.default_preset || 'overview_full_apartment';
let activePreset = cameras[activePresetName];
const eye = [...activePreset.position_m];
let yaw = activePreset.yaw;
let pitch = activePreset.pitch;
let fovDeg = activePreset.lens_mm <= 24 ? 62 : 54.4;
let zoomScale = activePreset.zoom_scale || 0.125;
let dragging = false;
let lastX = 0;
let lastY = 0;
let showGuides = false;
let showStaging = true;

function applyPreset(name) {
  activePresetName = name;
  activePreset = cameras[name];
  eye[0] = activePreset.position_m[0];
  eye[1] = activePreset.position_m[1];
  eye[2] = activePreset.position_m[2];
  yaw = activePreset.yaw;
  pitch = activePreset.pitch;
  fovDeg = activePreset.lens_mm <= 24 ? 62 : 54.4;
  zoomScale = activePreset.zoom_scale || 0.125;
  draw();
}

function resize() {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  draw();
}

function cameraTransform(p) {
  const dx = p[0] - eye[0];
  const dy = p[1] - eye[1];
  const dz = p[2] - eye[2];

  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const forward = dx * cy + dy * sy;
  const right = -dx * sy + dy * cy;

  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const forward2 = forward * cp + dz * sp;
  const up = -forward * sp + dz * cp;

  return [right, up, forward2];
}

function project(p) {
  const q = cameraTransform(p);
  if (q[2] <= 0.08) return null;
  const rect = canvas.getBoundingClientRect();
  const focal = rect.width / (2 * Math.tan((fovDeg * Math.PI / 180) / 2));
  const scaledFocal = focal * zoomScale;
  return [
    rect.width/2 + (q[0]/q[2])*scaledFocal,
    rect.height/2 - (q[1]/q[2])*scaledFocal,
    q[2]
  ];
}

function boxVertices(o) {
  const [x,y,z] = o.origin_m;
  const [w,d,h] = o.size_m;
  return [
    [x,y,z],[x+w,y,z],[x+w,y+d,z],[x,y+d,z],
    [x,y,z+h],[x+w,y,z+h],[x+w,y+d,z+h],[x,y+d,z+h]
  ];
}

const faces = [
  [0,1,2,3],[4,5,6,7],[0,1,5,4],
  [1,2,6,5],[2,3,7,6],[3,0,4,7]
];

const faceNormals = [
  [0,0,-1],[0,0,1],[0,-1,0],[1,0,0],[0,1,0],[-1,0,0]
];

function hexToRgb(hex) {
  const value = hex.replace('#','');
  return [
    parseInt(value.slice(0,2),16),
    parseInt(value.slice(2,4),16),
    parseInt(value.slice(4,6),16)
  ];
}

function rgbToCss(rgb) {
  return 'rgb(' + rgb.map(x => Math.max(0,Math.min(255,Math.round(x)))).join(',') + ')';
}

function materialFor(o) {
  if (visual.materials[o.material_id]) return visual.materials[o.material_id];
  return {base_color:'#e8e2d9', roughness:.8};
}

function lightFactor(normal, depth) {
  const ambient = visual.lighting.ambient_intensity;
  const sun = visual.lighting.sun_direction;
  const len = Math.hypot(...sun) || 1;
  const s = sun.map(v => v/len);
  const directional = Math.max(0, -(normal[0]*s[0] + normal[1]*s[1] + normal[2]*s[2]));
  const distanceFade = Math.max(.72, 1 - depth*.018);
  return Math.min(1.18, (ambient + directional*.62) * distanceFade);
}

function shadedColor(base, factor) {
  const rgb = hexToRgb(base);
  return rgbToCss(rgb.map(v => v * factor));
}

function drawWoodGrain(pts, depth) {
  if (!pts || pts.length < 4) return;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(pts[0][0],pts[0][1]);
  for (let i=1;i<pts.length;i++) ctx.lineTo(pts[i][0],pts[i][1]);
  ctx.closePath();
  ctx.clip();

  const minY = Math.min(...pts.map(p=>p[1]));
  const maxY = Math.max(...pts.map(p=>p[1]));
  ctx.strokeStyle = 'rgba(90,60,28,.10)';
  ctx.lineWidth = Math.max(.5, 1.2 - depth*.02);
  for (let y=minY; y<=maxY; y+=12) {
    ctx.beginPath();
    ctx.moveTo(Math.min(...pts.map(p=>p[0])), y);
    ctx.lineTo(Math.max(...pts.map(p=>p[0])), y+3);
    ctx.stroke();
  }
  ctx.restore();
}

function drawSoftShadow(o) {
  if (o.type !== 'staging_box') return;
  const p = project([o.origin_m[0]+o.size_m[0]/2, o.origin_m[1]+o.size_m[1]/2, 0.01]);
  if (!p) return;
  const scale = Math.max(8, 120 / p[2]);
  const g = ctx.createRadialGradient(p[0],p[1],2,p[0],p[1],scale);
  g.addColorStop(0,'rgba(0,0,0,.18)');
  g.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.ellipse(p[0],p[1],scale,scale*.28,0,0,Math.PI*2);
  ctx.fill();
}

function drawBox(o) {
  const vertices = boxVertices(o);
  const visible = [];

  for (let fi=0; fi<faces.length; fi++) {
    const pts = faces[fi].map(i => project(vertices[i]));
    if (pts.some(p => p === null)) continue;
    const depth = pts.reduce((sum,p)=>sum+p[2],0)/pts.length;
    visible.push({fi,pts,depth});
  }
  visible.sort((a,b)=>b.depth-a.depth);

  const mat = materialFor(o);

  for (const face of visible) {
    const pts = face.pts;
    ctx.beginPath();
    ctx.moveTo(pts[0][0],pts[0][1]);
    for (let i=1;i<pts.length;i++) ctx.lineTo(pts[i][0],pts[i][1]);
    ctx.closePath();

    const factor = lightFactor(faceNormals[face.fi], face.depth);
    ctx.fillStyle = shadedColor(mat.base_color, factor);
    ctx.fill();

    if (o.type === 'room_floor' && face.fi === 1) {
      drawWoodGrain(pts, face.depth);
    }

    ctx.strokeStyle = showGuides ? 'rgba(31,41,55,.72)' : 'rgba(31,41,55,.12)';
    ctx.lineWidth = showGuides ? 1.0 : .45;
    ctx.stroke();
  }
}

function drawWindowGlow() {
  const opening = scene.openings.find(x => x.type === 'window');
  if (!opening) return;

  const mid = [
    (opening.x1_cm + opening.x2_cm)/200,
    (opening.y1_cm + opening.y2_cm)/200 + .08,
    (opening.sill_cm + opening.height_cm*.55)/100
  ];
  const p = project(mid);
  if (!p) return;

  const rect = canvas.getBoundingClientRect();
  const radius = Math.max(90, Math.min(rect.width*.34, 440/p[2]));
  const g = ctx.createRadialGradient(p[0],p[1],8,p[0],p[1],radius);
  g.addColorStop(0,'rgba(255,244,220,.42)');
  g.addColorStop(.45,'rgba(255,239,210,.18)');
  g.addColorStop(1,'rgba(255,239,210,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0,0,rect.width,rect.height);
}

function drawBackground() {
  const rect = canvas.getBoundingClientRect();
  const sky = ctx.createLinearGradient(0,0,0,rect.height);
  sky.addColorStop(0,'#cfddea');
  sky.addColorStop(.42,'#eef1f2');
  sky.addColorStop(1,'#d8d0c4');
  ctx.fillStyle = sky;
  ctx.fillRect(0,0,rect.width,rect.height);
}

function drawVignette() {
  const rect = canvas.getBoundingClientRect();
  const g = ctx.createRadialGradient(
    rect.width/2,rect.height/2,rect.height*.18,
    rect.width/2,rect.height/2,rect.height*.68
  );
  g.addColorStop(0,'rgba(255,255,255,0)');
  g.addColorStop(1,'rgba(12,18,24,.16)');
  ctx.fillStyle = g;
  ctx.fillRect(0,0,rect.width,rect.height);
}

function draw() {
  drawBackground();

  const ordered = scene.objects
    .filter(o => showStaging || o.type !== 'staging_box')
    .map(o => {
      const c = [
        o.origin_m[0]+o.size_m[0]/2,
        o.origin_m[1]+o.size_m[1]/2,
        o.origin_m[2]+o.size_m[2]/2
      ];
      return {o, depth:cameraTransform(c)[2]};
    })
    .filter(x => x.depth > -1)
    .sort((a,b)=>b.depth-a.depth);

  for (const item of ordered) drawSoftShadow(item.o);
  for (const item of ordered) drawBox(item.o);

  drawWindowGlow();
  drawVignette();
}

canvas.addEventListener('mousedown', e => {
  dragging=true; lastX=e.clientX; lastY=e.clientY;
});
window.addEventListener('mouseup', () => dragging=false);
window.addEventListener('mousemove', e => {
  if (!dragging) return;
  yaw += (e.clientX-lastX)*.0035;
  pitch -= (e.clientY-lastY)*.0035;
  pitch = Math.max(-.8,Math.min(.8,pitch));
  lastX=e.clientX; lastY=e.clientY;
  draw();
});
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  zoomScale *= e.deltaY > 0 ? 0.90 : 1.10;
  zoomScale = Math.max(0.0625, Math.min(1.50, zoomScale));
  draw();
},{passive:false});

document.getElementById('reset').addEventListener('click', () => {
  applyPreset(activePresetName);
});
document.getElementById('presetOverview').addEventListener('click', () => {
  applyPreset('overview_full_apartment');
});
document.getElementById('presetLiving').addEventListener('click', () => {
  applyPreset('interior_living');
});
document.getElementById('toggleStaging').addEventListener('click', () => {
  showStaging=!showStaging; draw();
});
document.getElementById('toggleGuides').addEventListener('click', () => {
  showGuides=!showGuides; draw();
});

window.addEventListener('resize',resize);
resize();
</script>
</body>
</html>
"""
    return template.replace("__PAYLOAD_JSON__", payload_json)


def render_material_scene(scene_path, output_path):
    scene_path = Path(scene_path)
    output_path = Path(output_path)

    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    html = build_html(scene)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main():
    from geometry.test_floorplan_pipeline import (
        build_3d_scene,
        parse_test_floorplan,
        save_json,
    )

    source = Path("fixtures/floorplans/test_apartment.svg")
    scene_path = Path("build/test_floorplan_scene3d.json")
    output_path = Path("build/test_floorplan_materials_lighting.html")

    geometry = parse_test_floorplan(source)
    scene = build_3d_scene(geometry)
    save_json(scene, scene_path)

    rendered = render_material_scene(scene_path, output_path)
    preset = scene["visualization_preset"]

    print("--- ETAP 5E: MATERIAŁY I ŚWIATŁO ---")
    print("Źródło praw: OWN_TEST_ASSET")
    print("Walidacja geometrii: PASS")
    print(f"Preset wizualny: {preset['status']}")
    print("Materiały: ciepła biel + jasny dąb")
    print("Światło: ambient + symulowane światło okienne")
    print("Meble: TEST_STAGING")
    print(f"Wizualizacja: {rendered}")


if __name__ == "__main__":
    main()
