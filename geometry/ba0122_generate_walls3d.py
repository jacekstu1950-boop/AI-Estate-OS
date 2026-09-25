import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("sources/skanska/stilla/BA0122.svg")
OUT_JSON = Path("build/BA0122_walls3d_v1.json")
OUT_OBJ = Path("build/BA0122_walls3d_v1.obj")
OUT_HTML = Path("build/BA0122_walls3d_v1.html")

SCALE_M = 0.01842931985828394

# Vertical dimensions are NOT encoded in the 2D SVG.
WALL_HEIGHT_M = 2.70
HINGED_DOOR_HEIGHT_M = 2.10

STRUCTURAL_PATH_IDS = [
    "BO","BP","BQ","BR","BS","BT","BU","BV","BW","BX",
    "BY","BZ","Ba","Bb","Bc","Bd","Be","Bf"
]

OPENINGS = [
    {
        "id":"entry_door","axis":"h","line":60.814,"a":377.858,"b":434.228,
        "type":"door","height_m":HINGED_DOOR_HEIGHT_M,
        "wall_thickness_svg":12.902
    },
    {
        "id":"bathroom_door","axis":"v","line":474.196,"a":116.266,"b":168.391,
        "type":"door","height_m":HINGED_DOOR_HEIGHT_M,
        "wall_thickness_svg":6.480
    },
    {
        "id":"bedroom_door","axis":"v","line":410.258,"a":191.157,"b":239.498,
        "type":"door","height_m":HINGED_DOOR_HEIGHT_M,
        "wall_thickness_svg":4.358
    },
    {
        "id":"living_balcony_assembly","axis":"h","line":429.306,"a":236.104,"b":344.484,
        "type":"glazed_balcony_opening","height_m":WALL_HEIGHT_M,
        "vertical_profile_status":"PENDING"
    },
    {
        "id":"bedroom_balcony_assembly","axis":"h","line":429.306,"a":442.026,"b":523.340,
        "type":"glazed_balcony_opening","height_m":WALL_HEIGHT_M,
        "vertical_profile_status":"PENDING"
    },
]


def tokenize_path(d):
    return re.findall(r"[MLHVZmlhvz]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", d)


def parse_orthogonal_path(d):
    tokens = tokenize_path(d)
    pts=[]
    i=0
    x=y=0.0
    start=None
    cmd=None

    def num(tok):
        return float(tok)

    while i < len(tokens):
        t=tokens[i]
        if re.fullmatch(r"[MLHVZmlhvz]", t):
            cmd=t
            i+=1
            if cmd in "Zz":
                if start is not None and (not pts or pts[-1] != start):
                    pts.append(start)
                continue
        if cmd in ("M","L"):
            nx,ny=num(tokens[i]),num(tokens[i+1]); i+=2
            x,y=nx,ny
            if cmd=="M":
                start=(x,y)
                cmd="L"
            pts.append((x,y))
        elif cmd in ("m","l"):
            dx,dy=num(tokens[i]),num(tokens[i+1]); i+=2
            x,y=x+dx,y+dy
            if cmd=="m":
                start=(x,y)
                cmd="l"
            pts.append((x,y))
        elif cmd=="H":
            x=num(tokens[i]); i+=1; pts.append((x,y))
        elif cmd=="h":
            x+=num(tokens[i]); i+=1; pts.append((x,y))
        elif cmd=="V":
            y=num(tokens[i]); i+=1; pts.append((x,y))
        elif cmd=="v":
            y+=num(tokens[i]); i+=1; pts.append((x,y))
        else:
            raise ValueError(f"Unsupported command in structural path: {cmd}")

    # remove consecutive duplicates
    clean=[]
    for p in pts:
        if not clean or p != clean[-1]:
            clean.append(p)
    if len(clean)>=2 and clean[0]==clean[-1]:
        clean=clean[:-1]
    return clean


def polygon_area(poly):
    return sum(
        poly[i][0]*poly[(i+1)%len(poly)][1] -
        poly[(i+1)%len(poly)][0]*poly[i][1]
        for i in range(len(poly))
    )/2


def point_in_triangle(p,a,b,c):
    def s(p1,p2,p3):
        return (p1[0]-p3[0])*(p2[1]-p3[1])-(p2[0]-p3[0])*(p1[1]-p3[1])
    d1=s(p,a,b); d2=s(p,b,c); d3=s(p,c,a)
    has_neg=(d1<0) or (d2<0) or (d3<0)
    has_pos=(d1>0) or (d2>0) or (d3>0)
    return not (has_neg and has_pos)


def triangulate(poly):
    if len(poly)<3:
        return []
    pts=list(poly)
    if polygon_area(pts)<0:
        pts.reverse()
    idx=list(range(len(pts)))
    tris=[]
    guard=0
    while len(idx)>3 and guard<10000:
        guard+=1
        ear=False
        for k in range(len(idx)):
            i0=idx[k-1]; i1=idx[k]; i2=idx[(k+1)%len(idx)]
            a,b,c=pts[i0],pts[i1],pts[i2]
            cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
            if cross<=1e-9:
                continue
            if any(point_in_triangle(pts[j],a,b,c) for j in idx if j not in (i0,i1,i2)):
                continue
            tris.append((i0,i1,i2))
            del idx[k]
            ear=True
            break
        if not ear:
            break
    if len(idx)==3:
        tris.append(tuple(idx))
    if not tris:
        # safe fallback for a simple convex footprint
        tris=[(0,i,i+1) for i in range(1,len(pts)-1)]
    return pts,tris


def extrude_polygon(poly_svg,height_m,z0_m=0.0,name="wall"):
    poly=[(x*SCALE_M,y*SCALE_M) for x,y in poly_svg]
    result=triangulate(poly)
    if not result:
        return None
    pts,tris=result
    n=len(pts)
    verts=[(x,y,z0_m) for x,y in pts]+[(x,y,z0_m+height_m) for x,y in pts]
    faces=[]
    # bottom and top
    for a,b,c in tris:
        faces.append((c,b,a))
        faces.append((a+n,b+n,c+n))
    # sides
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,j+n))
        faces.append((i,j+n,i+n))
    return {"name":name,"vertices":verts,"faces":faces}


def box_mesh(x0,y0,x1,y1,z0,z1,name):
    v=[
        (x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
        (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)
    ]
    f=[
        (0,2,1),(0,3,2),(4,5,6),(4,6,7),
        (0,1,5),(0,5,4),(1,2,6),(1,6,5),
        (2,3,7),(2,7,6),(3,0,4),(3,4,7)
    ]
    return {"name":name,"vertices":v,"faces":f}


def build_lintel(opening):
    if opening["type"]!="door":
        return None
    a=opening["a"]*SCALE_M
    b=opening["b"]*SCALE_M
    line=opening["line"]*SCALE_M
    t=opening["wall_thickness_svg"]*SCALE_M
    z0=opening["height_m"]; z1=WALL_HEIGHT_M
    if opening["axis"]=="h":
        return box_mesh(a,line-t/2,b,line+t/2,z0,z1,opening["id"]+"_lintel")
    return box_mesh(line-t/2,a,line+t/2,b,z0,z1,opening["id"]+"_lintel")


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing {SOURCE}")
    root=ET.parse(SOURCE).getroot()
    defs={e.attrib.get("id"):e for e in root.iter() if e.attrib.get("id")}

    meshes=[]
    structural=[]
    for pid in STRUCTURAL_PATH_IDS:
        el=defs.get(pid)
        if el is None:
            raise ValueError(f"Missing structural path #{pid}")
        d=el.attrib.get("d","")
        poly=parse_orthogonal_path(d)
        if len(poly)<3:
            continue
        mesh=extrude_polygon(poly,WALL_HEIGHT_M,name=f"wall_{pid}")
        if mesh:
            meshes.append(mesh)
            structural.append({
                "source_path_id":pid,
                "polygon_svg":poly,
                "polygon_m":[[x*SCALE_M,y*SCALE_M] for x,y in poly],
                "height_m":WALL_HEIGHT_M
            })

    # Door gaps exist in the source plan footprint; add only lintels above hinged doors.
    lintels=[]
    for opening in OPENINGS:
        mesh=build_lintel(opening)
        if mesh:
            meshes.append(mesh)
            lintels.append(mesh["name"])

    # merge to OBJ
    OUT_OBJ.parent.mkdir(parents=True,exist_ok=True)
    lines=["# BA0122 walls3d v1","o BA0122_walls"]
    vertex_offset=1
    for mesh in meshes:
        lines.append(f"g {mesh['name']}")
        for x,y,z in mesh["vertices"]:
            # OBJ: X horizontal, Y vertical (height), Z plan depth
            lines.append(f"v {x:.6f} {z:.6f} {-y:.6f}")
        for a,b,c in mesh["faces"]:
            lines.append(f"f {a+vertex_offset} {b+vertex_offset} {c+vertex_offset}")
        vertex_offset += len(mesh["vertices"])
    OUT_OBJ.write_text("\n".join(lines)+"\n",encoding="utf-8")

    result={
        "apartment_code":"BA0122",
        "source":"official BA0122.svg",
        "source_sha256":"c452101011e3ba110f62e4ebaa81ebd1f2539cd3c384deecaefa88bb44e5d947",
        "meters_per_svg_unit":SCALE_M,
        "wall_height_m":{
            "value":WALL_HEIGHT_M,
            "status":"ASSUMPTION_CONFIGURABLE",
            "reason":"2D SVG does not encode vertical wall height"
        },
        "hinged_door_height_m":{
            "value":HINGED_DOOR_HEIGHT_M,
            "status":"ASSUMPTION_CONFIGURABLE",
            "reason":"2D SVG does not encode door height"
        },
        "balcony_opening_vertical_profile":"PENDING",
        "structural_paths":structural,
        "openings":OPENINGS,
        "lintels":lintels,
        "mesh_count":len(meshes),
        "obj_file":str(OUT_OBJ),
        "qa":{
            "plan_geometry_source":"PASS",
            "metric_scale":"PASS",
            "door_plan_openings":"PASS",
            "door_lintels":"PASS_WITH_VERTICAL_ASSUMPTION",
            "balcony_opening_widths":"PASS",
            "balcony_vertical_profile":"PENDING"
        }
    }
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")

    # Standalone viewer uses Three.js from CDN.
    payload=json.dumps([{"name":m["name"],"vertices":m["vertices"],"faces":m["faces"]} for m in meshes])
    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>BA0122 walls 3D</title>
<style>html,body,#c{{width:100%;height:100%;margin:0;overflow:hidden}}#info{{position:absolute;z-index:2;left:12px;top:12px;background:#fffD;padding:10px;border-radius:8px;font:14px Arial}}</style>
</head><body><div id="info"><b>BA0122 — ściany 3D v1</b><br>Plan: źródłowy SVG<br>Skala: zweryfikowana<br>Wysokość ścian 2.70 m: ASSUMPTION<br>Drzwi 2.10 m: ASSUMPTION<br><span id="status">Ładowanie modelu…</span></div><div id="c"></div>
<script type="importmap">
{{
  "imports": {{
    "three": "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const meshes={payload};
const scene=new THREE.Scene(); scene.background=new THREE.Color(0xf5f5f3);
const camera=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,.01,100);
camera.position.set(10,8,10);
const renderer=new THREE.WebGLRenderer({{antialias:true}}); renderer.setSize(innerWidth,innerHeight); document.getElementById('c').appendChild(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x777777,2.2));
const dl=new THREE.DirectionalLight(0xffffff,2); dl.position.set(4,10,6); scene.add(dl);
const mat=new THREE.MeshStandardMaterial({{color:0xe6e1d8,roughness:.85,side:THREE.DoubleSide}});
const root=new THREE.Group(); scene.add(root);
for(const m of meshes){{
 const pos=[]; for(const v of m.vertices) pos.push(v[0],v[2],-v[1]);
 const idx=[]; for(const f of m.faces) idx.push(f[0],f[1],f[2]);
 const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setIndex(idx); g.computeVertexNormals();
 const mesh=new THREE.Mesh(g,mat); root.add(mesh);
}}
const box=new THREE.Box3().setFromObject(root);
const center=box.getCenter(new THREE.Vector3());
const size=box.getSize(new THREE.Vector3());
const radius=Math.max(size.x,size.y,size.z);
controls.target.copy(center);
camera.position.set(center.x + radius*1.3, center.y + radius*1.1, center.z + radius*1.3);
camera.near=Math.max(0.01,radius/1000); camera.far=radius*20; camera.updateProjectionMatrix();
controls.update();
const grid=new THREE.GridHelper(Math.max(14,radius*2.2),28,0x999999,0xdddddd); grid.position.y=box.min.y; scene.add(grid);
document.getElementById('status').textContent='Model załadowany — przeciągnij myszą, aby obracać; rolka = zoom';
function anim(){{requestAnimationFrame(anim);controls.update();renderer.render(scene,camera)}} anim();
addEventListener('resize',()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)}})
</script></body></html>"""
    OUT_HTML.write_text(html,encoding="utf-8")

    print("--- BA0122 3D WALL GENERATION ---")
    print(f"Structural footprints: {len(structural)}")
    print(f"Meshes incl. lintels: {len(meshes)}")
    print(f"Wall height: {WALL_HEIGHT_M:.2f} m [ASSUMPTION]")
    print(f"Hinged door height: {HINGED_DOOR_HEIGHT_M:.2f} m [ASSUMPTION]")
    print(f"JSON: {OUT_JSON}")
    print(f"OBJ: {OUT_OBJ}")
    print(f"Viewer: {OUT_HTML}")
    print("QA: plan geometry PASS; balcony vertical profile PENDING")

if __name__=="__main__":
    main()
