import json
from pathlib import Path


def build_html(scene):
    if scene.get("source_rights_status") != "OWN_TEST_ASSET":
        raise ValueError("Renderer 3D działa wyłącznie dla OWN_TEST_ASSET.")

    if scene.get("geometry_validation", {}).get("status") != "PASS":
        raise ValueError("Scena 3D nie przeszła walidacji geometrii.")

    scene_json = json.dumps(scene, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Estate-OS — testowy renderer 3D</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f5f7fa;
    color: #1f2937;
  }}
  header {{
    background: #111827;
    color: white;
    padding: 18px 22px;
  }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  .card {{
    background: white;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }}
  #viewport {{
    width: 100%;
    height: 680px;
    display: block;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    background: white;
    cursor: grab;
  }}
  #viewport:active {{ cursor: grabbing; }}
  .toolbar {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 12px;
  }}
  button {{
    border: 1px solid #d1d5db;
    background: #111827;
    color: white;
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 700;
    cursor: pointer;
  }}
  .status {{
    margin-left: auto;
    color: #047857;
    font-weight: 700;
  }}
  .muted {{ color: #6b7280; }}
</style>
</head>
<body>
<header>
  <h1>AI-Estate-OS — testowy renderer 3D</h1>
  <div>Własny syntetyczny rzut testowy — ściany, drzwi i okna</div>
</header>
<main>
  <div class="card">
    <div class="toolbar">
      <button id="resetView" type="button">Widok domyślny</button>
      <button id="topView" type="button">Widok z góry</button>
      <span class="muted">Przeciągnij myszą, aby obracać. Rolka zmienia skalę.</span>
      <span class="status">OWN_TEST_ASSET · geometria PASS</span>
    </div>
    <canvas id="viewport"></canvas>
  </div>
</main>

<script>
const scene = {scene_json};
const canvas = document.getElementById('viewport');
const ctx = canvas.getContext('2d');

let yaw = -0.65;
let pitch = 0.62;
let zoom = 78;
let dragging = false;
let lastX = 0;
let lastY = 0;

function resize() {{
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}}

function bounds() {{
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const o of scene.objects) {{
    minX = Math.min(minX, o.origin_m[0]);
    minY = Math.min(minY, o.origin_m[1]);
    maxX = Math.max(maxX, o.origin_m[0] + o.size_m[0]);
    maxY = Math.max(maxY, o.origin_m[1] + o.size_m[1]);
  }}
  return {{
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2
  }};
}}

const center = bounds();

function rotatePoint(p) {{
  let x = p[0] - center.cx;
  let y = p[1] - center.cy;
  let z = p[2];

  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const x1 = x * cy - y * sy;
  const y1 = x * sy + y * cy;

  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const y2 = y1 * cp - z * sp;
  const z2 = y1 * sp + z * cp;

  return [x1, y2, z2];
}}

function project(p) {{
  const q = rotatePoint(p);
  const rect = canvas.getBoundingClientRect();
  const depth = 12 + q[2];
  const perspective = 12 / Math.max(3, depth);
  return [
    rect.width / 2 + q[0] * zoom * perspective,
    rect.height / 2 - q[1] * zoom * perspective
  ];
}}

function boxVertices(o) {{
  const [x,y,z] = o.origin_m;
  const [w,d,h] = o.size_m;
  return [
    [x,y,z],[x+w,y,z],[x+w,y+d,z],[x,y+d,z],
    [x,y,z+h],[x+w,y,z+h],[x+w,y+d,z+h],[x,y+d,z+h]
  ];
}}

const faces = [
  [0,1,2,3],
  [4,5,6,7],
  [0,1,5,4],
  [1,2,6,5],
  [2,3,7,6],
  [3,0,4,7]
];

function depthOfFace(vertices, face) {{
  return face.reduce((sum, i) => sum + rotatePoint(vertices[i])[2], 0) / face.length;
}}

function drawBox(o, index) {{
  const vertices = boxVertices(o);
  const orderedFaces = faces
    .map(face => ({{ face, depth: depthOfFace(vertices, face) }}))
    .sort((a,b) => a.depth - b.depth);

  for (const entry of orderedFaces) {{
    const pts = entry.face.map(i => project(vertices[i]));
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();

    const shade = 92 - (index % 4) * 5;
    ctx.fillStyle = `hsl(${{205 + index * 24}} 35% ${{shade}}%)`;
    ctx.fill();
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }}

  if (o.type === 'room_floor') {
    const label = project([
      o.origin_m[0] + o.size_m[0] / 2,
      o.origin_m[1] + o.size_m[1] / 2,
      0.08
    ]);
    ctx.fillStyle = '#111827';
    ctx.font = '600 13px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(o.name, label[0], label[1]);
  }
}}

function drawGround() {{
  const rect = canvas.getBoundingClientRect();
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, rect.width, rect.height);

  ctx.strokeStyle = '#e5e7eb';
  ctx.lineWidth = 1;
  for (let i = -8; i <= 8; i++) {{
    const a = project([center.cx + i, center.cy - 8, 0]);
    const b = project([center.cx + i, center.cy + 8, 0]);
    ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.stroke();

    const c = project([center.cx - 8, center.cy + i, 0]);
    const d = project([center.cx + 8, center.cy + i, 0]);
    ctx.beginPath(); ctx.moveTo(c[0],c[1]); ctx.lineTo(d[0],d[1]); ctx.stroke();
  }}
}}

function draw() {{
  drawGround();
  const ordered = scene.objects
    .map((o, i) => ({{ o, i, z: rotatePoint([
      o.origin_m[0] + o.size_m[0]/2,
      o.origin_m[1] + o.size_m[1]/2,
      o.size_m[2]/2
    ])[2] }}))
    .sort((a,b) => a.z - b.z);

  for (const item of ordered) drawBox(item.o, item.i);
}}

canvas.addEventListener('mousedown', e => {{
  dragging = true; lastX = e.clientX; lastY = e.clientY;
}});
window.addEventListener('mouseup', () => dragging = false);
window.addEventListener('mousemove', e => {{
  if (!dragging) return;
  yaw += (e.clientX - lastX) * 0.008;
  pitch += (e.clientY - lastY) * 0.008;
  pitch = Math.max(-1.45, Math.min(1.45, pitch));
  lastX = e.clientX; lastY = e.clientY;
  draw();
}});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  zoom *= e.deltaY > 0 ? 0.92 : 1.08;
  zoom = Math.max(30, Math.min(180, zoom));
  draw();
}}, {{passive:false}});

document.getElementById('resetView').addEventListener('click', () => {{
  yaw = -0.65; pitch = 0.62; zoom = 78; draw();
}});
document.getElementById('topView').addEventListener('click', () => {{
  yaw = 0; pitch = 1.45; zoom = 76; draw();
}});

window.addEventListener('resize', resize);
resize();
</script>
</body>
</html>
"""


def render_scene_file(scene_path, output_path):
    scene_path = Path(scene_path)
    output_path = Path(output_path)

    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    html = build_html(scene)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main():
    scene_path = Path("build/test_floorplan_scene3d.json")
    output_path = Path("build/test_floorplan_3d.html")

    if not scene_path.exists():
        from geometry.test_floorplan_pipeline import (
            build_3d_scene,
            parse_test_floorplan,
            save_json,
        )

        source = Path("fixtures/floorplans/test_apartment.svg")
        geometry = parse_test_floorplan(source)
        scene = build_3d_scene(geometry)
        save_json(scene, scene_path)

    rendered = render_scene_file(scene_path, output_path)

    print("--- TESTOWY RENDERER 3D ---")
    print("Źródło praw: OWN_TEST_ASSET")
    print("Walidacja geometrii: PASS")
    print(f"Podgląd 3D: {rendered}")
    print("Otwórz plik w przeglądarce, aby obracać model myszą.")


if __name__ == "__main__":
    main()
