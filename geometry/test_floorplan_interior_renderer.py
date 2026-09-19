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
        raise ValueError("Renderer wnętrza działa wyłącznie dla OWN_TEST_ASSET.")
    if scene.get("geometry_validation", {}).get("status") != "PASS":
        raise ValueError("Scena 3D nie przeszła walidacji geometrii.")

    camera = scene.get("camera_presets", {}).get("interior_living")
    if not camera:
        raise ValueError("Brak presetu kamery interior_living.")
    if camera.get("status") != "TEST_PRESET":
        raise ValueError("Preset kamery nie jest oznaczony jako TEST_PRESET.")

    yaw, pitch = _camera_angles(camera["position_m"], camera["target_m"])
    payload = {
        "scene": scene,
        "camera": {
            **camera,
            "yaw": yaw,
            "pitch": pitch,
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    template = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Estate-OS — testowa kamera wnętrza</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family:Arial,sans-serif; background:#eceff3; color:#1f2937; }
  header { background:#111827; color:#fff; padding:18px 22px; }
  header h1 { margin:0 0 5px; font-size:22px; }
  main { max-width:1280px; margin:0 auto; padding:20px; }
  .card { background:#fff; border-radius:14px; padding:16px; box-shadow:0 2px 10px rgba(0,0,0,.09); }
  .toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  button { border:1px solid #d1d5db; background:#111827; color:#fff; border-radius:8px; padding:9px 12px; font-weight:700; cursor:pointer; }
  .muted { color:#6b7280; }
  .status { margin-left:auto; color:#047857; font-weight:700; }
  #viewport { width:100%; height:720px; display:block; border:1px solid #d1d5db; border-radius:10px; cursor:grab; }
  #viewport:active { cursor:grabbing; }
</style>
</head>
<body>
<header>
  <h1>AI-Estate-OS — pierwsza testowa wizualizacja wnętrza</h1>
  <div>Własny rzut testowy · kamera 35 mm · wysokość oka 1,65 m</div>
</header>
<main>
  <div class="card">
    <div class="toolbar">
      <button id="reset" type="button">Kamera startowa</button>
      <button id="wire" type="button">Linie pomocnicze</button>
      <span class="muted">Przeciągnij myszą, aby rozglądać się. Rolka zmienia pole widzenia.</span>
      <span class="status">OWN_TEST_ASSET · TEST_PRESET · PASS</span>
    </div>
    <canvas id="viewport"></canvas>
  </div>
</main>
<script>
const payload = __PAYLOAD_JSON__;
const scene = payload.scene;
const preset = payload.camera;
const canvas = document.getElementById('viewport');
const ctx = canvas.getContext('2d');

const eye = [...preset.position_m];
let yaw = preset.yaw;
let pitch = preset.pitch;
let fovDeg = 54.4;
let dragging = false;
let lastX = 0;
let lastY = 0;
let wire = false;

function resize() {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
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
  return [
    rect.width / 2 + (q[0] / q[2]) * focal,
    rect.height / 2 - (q[1] / q[2]) * focal,
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

function shadeForFace(faceIndex, type) {
  if (type === 'room_floor') {
    return faceIndex === 1 ? '#d8c6a3' : '#c8b58f';
  }
  const wallShades = ['#ece7df','#f5f1ea','#ddd7cf','#e7e1d9','#d7d1c9','#eee9e2'];
  return wallShades[faceIndex % wallShades.length];
}

function drawBox(o) {
  const vertices = boxVertices(o);
  const visible = [];

  for (let fi = 0; fi < faces.length; fi++) {
    const pts = faces[fi].map(i => project(vertices[i]));
    if (pts.some(p => p === null)) continue;
    const depth = pts.reduce((sum,p) => sum + p[2], 0) / pts.length;
    visible.push({ fi, pts, depth });
  }

  visible.sort((a,b) => b.depth - a.depth);

  for (const face of visible) {
    const pts = face.pts;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i=1; i<pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    ctx.fillStyle = shadeForFace(face.fi, o.type);
    ctx.fill();
    ctx.strokeStyle = wire ? '#374151' : 'rgba(55,65,81,.26)';
    ctx.lineWidth = wire ? 1.0 : 0.55;
    ctx.stroke();
  }
}

function drawBackground() {
  const rect = canvas.getBoundingClientRect();
  const gradient = ctx.createLinearGradient(0,0,0,rect.height);
  gradient.addColorStop(0,'#dfeaf2');
  gradient.addColorStop(0.55,'#f5f2eb');
  gradient.addColorStop(1,'#cfc6b6');
  ctx.fillStyle = gradient;
  ctx.fillRect(0,0,rect.width,rect.height);
}

function drawCrosshair() {
  const rect = canvas.getBoundingClientRect();
  ctx.strokeStyle = 'rgba(17,24,39,.22)';
  ctx.beginPath();
  ctx.moveTo(rect.width/2-7,rect.height/2);
  ctx.lineTo(rect.width/2+7,rect.height/2);
  ctx.moveTo(rect.width/2,rect.height/2-7);
  ctx.lineTo(rect.width/2,rect.height/2+7);
  ctx.stroke();
}

function draw() {
  drawBackground();

  const ordered = scene.objects
    .map(o => {
      const c = [
        o.origin_m[0] + o.size_m[0]/2,
        o.origin_m[1] + o.size_m[1]/2,
        o.origin_m[2] + o.size_m[2]/2
      ];
      return { o, depth: cameraTransform(c)[2] };
    })
    .filter(x => x.depth > -1.0)
    .sort((a,b) => b.depth - a.depth);

  for (const item of ordered) drawBox(item.o);
  drawCrosshair();
}

canvas.addEventListener('mousedown', e => {
  dragging = true; lastX = e.clientX; lastY = e.clientY;
});
window.addEventListener('mouseup', () => dragging = false);
window.addEventListener('mousemove', e => {
  if (!dragging) return;
  yaw += (e.clientX - lastX) * 0.004;
  pitch -= (e.clientY - lastY) * 0.004;
  pitch = Math.max(-0.85, Math.min(0.85, pitch));
  lastX = e.clientX; lastY = e.clientY;
  draw();
});
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  fovDeg *= e.deltaY > 0 ? 1.05 : 0.95;
  fovDeg = Math.max(32, Math.min(80, fovDeg));
  draw();
}, {passive:false});

document.getElementById('reset').addEventListener('click', () => {
  yaw = preset.yaw;
  pitch = preset.pitch;
  fovDeg = 54.4;
  draw();
});
document.getElementById('wire').addEventListener('click', () => {
  wire = !wire;
  draw();
});

window.addEventListener('resize', resize);
resize();
</script>
</body>
</html>
"""
    return template.replace("__PAYLOAD_JSON__", payload_json)


def render_interior(scene_path, output_path):
    scene_path = Path(scene_path)
    output_path = Path(output_path)

    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    html = build_html(scene)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main():
    scene_path = Path("build/test_floorplan_scene3d.json")
    output_path = Path("build/test_floorplan_interior_35mm.html")

    from geometry.test_floorplan_pipeline import (
        build_3d_scene,
        parse_test_floorplan,
        save_json,
    )

    source = Path("fixtures/floorplans/test_apartment.svg")
    geometry = parse_test_floorplan(source)
    scene = build_3d_scene(geometry)
    save_json(scene, scene_path)

    rendered = render_interior(scene_path, output_path)

    camera = scene["camera_presets"]["interior_living"]
    print("--- TESTOWA KAMERA WNĘTRZA 35 MM ---")
    print("Źródło praw: OWN_TEST_ASSET")
    print("Walidacja geometrii: PASS")
    print(f"Wysokość oka: {camera['eye_height_m']:.2f} m")
    print(f"Ogniskowa: {camera['lens_mm']} mm")
    print(f"Pozycja kamery: {camera['position_m']}")
    print(f"Cel kamery: {camera['target_m']}")
    print(f"Wizualizacja: {rendered}")


if __name__ == "__main__":
    main()
