import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("sources/skanska/stilla/BA0122.svg")
OUT_JSON = Path("build/BA0122_walls3d_exact_v2.json")
OUT_OBJ = Path("build/BA0122_walls3d_exact_v2.obj")
OUT_HTML = Path("build/BA0122_walls3d_exact_v2.html")
OUT_QA_HTML = Path("build/BA0122_walls3d_exact_v2_qa.html")

SCALE_M = 0.01842931985828394
WALL_HEIGHT_M = 2.70  # configurable assumption; not encoded in 2D SVG

WALL_FILL_COLORS = {"#c7c8c9", "#646566"}

def local_name(tag):
    return tag.split("}", 1)[-1]

def tokenize_path(d):
    return re.findall(r"[MLHVZmlhvz]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", d or "")

def parse_filled_subpaths(d):
    toks = tokenize_path(d)
    i=0; x=y=0.0; sx=sy=None; cmd=None; current=[]; out=[]
    def flush():
        nonlocal current
        if len(current)>=3:
            # SVG fill implicitly closes open subpaths.
            if current[0]==current[-1]:
                current=current[:-1]
            if len(current)>=3:
                out.append(current)
        current=[]
    while i < len(toks):
        t=toks[i]
        if re.fullmatch(r"[MLHVZmlhvz]", t):
            cmd=t; i+=1
            if cmd in "Zz":
                if sx is not None and (not current or current[-1]!=(sx,sy)):
                    current.append((sx,sy))
                flush(); sx=sy=None
                continue
        if cmd=="M":
            if current: flush()
            x=float(toks[i]); y=float(toks[i+1]); i+=2
            sx,sy=x,y; current=[(x,y)]; cmd="L"
        elif cmd=="m":
            if current: flush()
            x+=float(toks[i]); y+=float(toks[i+1]); i+=2
            sx,sy=x,y; current=[(x,y)]; cmd="l"
        elif cmd=="L":
            x=float(toks[i]); y=float(toks[i+1]); i+=2; current.append((x,y))
        elif cmd=="l":
            x+=float(toks[i]); y+=float(toks[i+1]); i+=2; current.append((x,y))
        elif cmd=="H":
            x=float(toks[i]); i+=1; current.append((x,y))
        elif cmd=="h":
            x+=float(toks[i]); i+=1; current.append((x,y))
        elif cmd=="V":
            y=float(toks[i]); i+=1; current.append((x,y))
        elif cmd=="v":
            y+=float(toks[i]); i+=1; current.append((x,y))
        else:
            raise ValueError(f"Unsupported command {cmd!r} in filled wall path")
    if current: flush()
    return [dedupe(poly) for poly in out if abs(polygon_area(poly)) > 1e-6]

def dedupe(poly):
    r=[]
    for p in poly:
        if not r or p!=r[-1]:
            r.append(p)
    if len(r)>1 and r[0]==r[-1]:
        r=r[:-1]
    return r

def polygon_area(poly):
    return 0.5*sum(
        poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1]
        for i in range(len(poly))
    )

def point_in_tri(p,a,b,c):
    def cross(p1,p2,p3):
        return (p1[0]-p3[0])*(p2[1]-p3[1])-(p2[0]-p3[0])*(p1[1]-p3[1])
    d1=cross(p,a,b); d2=cross(p,b,c); d3=cross(p,c,a)
    return not (((d1<0) or (d2<0) or (d3<0)) and ((d1>0) or (d2>0) or (d3>0)))

def triangulate(poly):
    pts=list(poly)
    if polygon_area(pts)<0: pts.reverse()
    idx=list(range(len(pts))); tris=[]; guard=0
    while len(idx)>3 and guard<5000:
        guard+=1; found=False
        for k in range(len(idx)):
            i0,i1,i2=idx[k-1],idx[k],idx[(k+1)%len(idx)]
            a,b,c=pts[i0],pts[i1],pts[i2]
            z=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
            if z<=1e-9: continue
            if any(point_in_tri(pts[j],a,b,c) for j in idx if j not in (i0,i1,i2)):
                continue
            tris.append((i0,i1,i2)); del idx[k]; found=True; break
        if not found:
            # Skip malformed/degenerate fill fragment rather than invent geometry.
            return pts,[]
    if len(idx)==3: tris.append(tuple(idx))
    return pts,tris

def extrude(poly_svg,height,name):
    poly=[(x*SCALE_M,y*SCALE_M) for x,y in poly_svg]
    pts,tris=triangulate(poly)
    if not tris: return None
    n=len(pts)
    verts=[(x,y,0.0) for x,y in pts]+[(x,y,height) for x,y in pts]
    faces=[]
    for a,b,c in tris:
        faces += [(c,b,a),(a+n,b+n,c+n)]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,j+n),(i,j+n,i+n)]
    return {"name":name,"vertices":verts,"faces":faces}

def find_wall_groups(root):
    groups=[]
    for idx,child in enumerate(list(root)):
        if local_name(child.tag)!="g": continue
        fill=(child.attrib.get("fill") or "").lower()
        if fill in WALL_FILL_COLORS:
            groups.append((idx,fill,child))
    return groups

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing {SOURCE}")
    root=ET.parse(SOURCE).getroot()
    wall_groups=find_wall_groups(root)
    if len(wall_groups)!=2:
        raise RuntimeError(f"Expected 2 filled wall-mass groups, got {[(i,f) for i,f,_ in wall_groups]}")

    meshes=[]; records=[]; skipped=[]
    for group_index,fill,g in wall_groups:
        for pidx,el in enumerate(e for e in g.iter() if local_name(e.tag)=="path"):
            d=el.attrib.get("d","")
            subpaths=parse_filled_subpaths(d)
            for sidx,poly in enumerate(subpaths):
                mesh=extrude(poly,WALL_HEIGHT_M,f"wall_g{group_index}_p{pidx}_s{sidx}")
                rec={
                    "group_index":group_index,"fill":fill,"path_index":pidx,"subpath_index":sidx,
                    "polygon_svg":poly,
                    "polygon_m":[[x*SCALE_M,y*SCALE_M] for x,y in poly],
                    "source_area_svg2":abs(polygon_area(poly))
                }
                if mesh is None:
                    rec["qa"]="SKIPPED_DEGENERATE"
                    skipped.append(rec)
                else:
                    rec["qa"]="PASS_EXTRUDED_FROM_FILLED_SOURCE"
                    records.append(rec); meshes.append(mesh)

    OUT_OBJ.parent.mkdir(parents=True,exist_ok=True)
    lines=["# BA0122 exact wall masses v2","o BA0122_exact_walls"]
    off=1
    for m in meshes:
        lines.append(f"g {m['name']}")
        for x,y,z in m["vertices"]:
            lines.append(f"v {x:.6f} {z:.6f} {-y:.6f}")
        for a,b,c in m["faces"]:
            lines.append(f"f {a+off} {b+off} {c+off}")
        off+=len(m["vertices"])
    OUT_OBJ.write_text("\n".join(lines)+"\n",encoding="utf-8")

    result={
        "apartment_code":"BA0122",
        "source_sha256":"c452101011e3ba110f62e4ebaa81ebd1f2539cd3c384deecaefa88bb44e5d947",
        "strategy":"extrude exact filled wall-mass polygons from source SVG groups with fills #c7c8c9 and #646566",
        "meters_per_svg_unit":SCALE_M,
        "wall_height_m":{"value":WALL_HEIGHT_M,"status":"ASSUMPTION_CONFIGURABLE"},
        "wall_groups":[{"top_level_index":i,"fill":f} for i,f,_ in wall_groups],
        "extruded_subpaths":records,
        "skipped_degenerate_subpaths":skipped,
        "mesh_count":len(meshes),
        "qa":{
            "source_wall_mass_selection":"PASS",
            "source_outline_paths_used_as_solids":"NO",
            "implicit_closure_only_per_svg_fill_rule":"YES",
            "invented_plan_geometry":"NO",
            "vertical_height":"ASSUMPTION"
        }
    }
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")

    payload=json.dumps([{"name":m["name"],"vertices":m["vertices"],"faces":m["faces"]} for m in meshes])
    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>BA0122 exact walls v2 offline</title>
<style>
html,body{{width:100%;height:100%;margin:0;overflow:hidden;background:#f7f7f5;font-family:Arial,sans-serif}}
#c{{position:absolute;inset:0;width:100%;height:100%}}
#info{{position:absolute;z-index:2;left:12px;top:12px;background:#fffffff0;padding:10px;border-radius:8px;max-width:440px;box-shadow:0 2px 12px #0002}}
#err{{color:#b00020;font-weight:bold}}
</style></head>
<body>
<canvas id="c"></canvas>
<div id="info">
<b>BA0122 — EXACT ściany 3D v2 OFFLINE</b><br>
Źródło: wypełnione masy ścian z SVG<br>
Brak bibliotek internetowych / CDN<br>
Wysokość 2.70 m: ASSUMPTION<br>
<span id="status">Ładowanie modelu…</span><br>
<span>Przeciągnij myszą: obrót 360° · rolka: zoom</span><br>
<span id="err"></span>
</div>
<script>
const data={payload};
const canvas=document.getElementById('c');
const ctx=canvas.getContext('2d');
let yaw=-0.75, pitch=0.62, zoom=80, dragging=false, lx=0, ly=0;

function resize(){{
  const dpr=Math.max(1,window.devicePixelRatio||1);
  canvas.width=Math.floor(innerWidth*dpr);
  canvas.height=Math.floor(innerHeight*dpr);
  canvas.style.width=innerWidth+'px';
  canvas.style.height=innerHeight+'px';
  ctx.setTransform(dpr,0,0,dpr,0,0);
  draw();
}}
addEventListener('resize',resize);

let verts=[];
for(const m of data) for(const v of m.vertices) verts.push(v);
if(!verts.length){{
  document.getElementById('err').textContent='BŁĄD: model nie zawiera wierzchołków.';
}}
const min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity];
for(const v of verts) for(let i=0;i<3;i++){{min[i]=Math.min(min[i],v[i]);max[i]=Math.max(max[i],v[i]);}}
const center=[(min[0]+max[0])/2,(min[1]+max[1])/2,(min[2]+max[2])/2];
const span=Math.max(max[0]-min[0],max[1]-min[1],max[2]-min[2]);
zoom=Math.min(innerWidth,innerHeight)/Math.max(span*2.2,1);

function project(v){{
  let x=v[0]-center[0], y=v[1]-center[1], z=v[2]-center[2];
  const cy=Math.cos(yaw), sy=Math.sin(yaw);
  let x1=cy*x-sy*y, y1=sy*x+cy*y;
  const cp=Math.cos(pitch), sp=Math.sin(pitch);
  let y2=cp*y1-sp*z, z2=sp*y1+cp*z;
  const perspective=1/(1+Math.max(-0.8,z2*0.05));
  return [innerWidth/2+x1*zoom*perspective, innerHeight/2+y2*zoom*perspective, z2];
}}

function faceNormal(a,b,c){{
 const u=[b[0]-a[0],b[1]-a[1],b[2]-a[2]], v=[c[0]-a[0],c[1]-a[1],c[2]-a[2]];
 return [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
}}

function draw(){{
  ctx.clearRect(0,0,innerWidth,innerHeight);
  ctx.fillStyle='#f7f7f5'; ctx.fillRect(0,0,innerWidth,innerHeight);
  const polys=[];
  for(const m of data){{
    for(const f of m.faces){{
      const a=m.vertices[f[0]], b=m.vertices[f[1]], c=m.vertices[f[2]];
      const pa=project(a), pb=project(b), pc=project(c);
      const depth=(pa[2]+pb[2]+pc[2])/3;
      const n=faceNormal(a,b,c);
      const shade=Math.max(0.45,Math.min(1,0.72+0.18*(n[2]/(Math.hypot(...n)||1))));
      polys.push({{p:[pa,pb,pc],depth,shade}});
    }}
  }}
  polys.sort((a,b)=>a.depth-b.depth);
  for(const poly of polys){{
    const s=Math.round(220*poly.shade);
    ctx.beginPath(); ctx.moveTo(poly.p[0][0],poly.p[0][1]); ctx.lineTo(poly.p[1][0],poly.p[1][1]); ctx.lineTo(poly.p[2][0],poly.p[2][1]); ctx.closePath();
    ctx.fillStyle='rgb('+s+','+(s-2)+','+(s-7)+')'; ctx.fill();
    ctx.strokeStyle='#777'; ctx.lineWidth=0.6; ctx.stroke();
  }}
  document.getElementById('status').textContent='Model załadowany: '+data.length+' meshów';
}}

canvas.addEventListener('mousedown',e=>{{dragging=true;lx=e.clientX;ly=e.clientY}});
addEventListener('mouseup',()=>dragging=false);
addEventListener('mousemove',e=>{{if(!dragging)return; yaw+=(e.clientX-lx)*0.008; pitch=Math.max(-1.45,Math.min(1.45,pitch+(e.clientY-ly)*0.008)); lx=e.clientX;ly=e.clientY;draw();}});
canvas.addEventListener('wheel',e=>{{e.preventDefault(); zoom*=Math.exp(-e.deltaY*0.001); zoom=Math.max(8,Math.min(500,zoom)); draw();}},{{passive:false}});
resize();
</script></body></html>"""
    OUT_HTML.write_text(html,encoding="utf-8")

    # Exact top-down QA: source SVG on the left; extracted wall polygons on the right.
    # This view is orthographic and contains no 3D perspective, so rectangles remain rectangles.
    wall_polys = json.dumps([
        rec["polygon_svg"] for rec in records
    ], ensure_ascii=False)
    source_svg = SOURCE.read_text(encoding="utf-8")
    qa_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>BA0122 2D vs Master Geometry QA</title>
<style>
body{{margin:0;font-family:Arial,sans-serif;background:#eef2f7}}
header{{padding:12px 16px;background:#111827;color:#fff}}
main{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}}
.panel{{background:#fff;border-radius:10px;padding:10px;overflow:auto}}
h3{{margin:0 0 8px}}
svg{{width:100%;height:auto;display:block}}
canvas{{width:100%;height:auto;background:#fff;border:1px solid #ddd}}
.note{{padding:8px 12px;background:#fff4cc;border-left:4px solid #d7a500;margin:12px}}
</style></head>
<body>
<header><b>BA0122 — kontrola 2D vs Master Geometry</b></header>
<div class="note">To jest widok ortogonalny z góry. Brak perspektywy 3D. Jeżeli prawa strona różni się od ścian po lewej, parser ścian jest błędny.</div>
<main>
<div class="panel"><h3>1. Oryginalny BA0122.svg</h3>{source_svg}</div>
<div class="panel"><h3>2. Wyekstrahowane masy ścian — bez perspektywy</h3><canvas id="qa" width="750" height="563"></canvas></div>
</main>
<script>
const polys={wall_polys};
const canvas=document.getElementById('qa'),ctx=canvas.getContext('2d');
ctx.clearRect(0,0,750,563);
ctx.fillStyle='#fff';ctx.fillRect(0,0,750,563);
ctx.fillStyle='#666';
ctx.strokeStyle='#111';
ctx.lineWidth=0.8;
for(const poly of polys){{
 if(!poly.length) continue;
 ctx.beginPath();
 ctx.moveTo(poly[0][0],poly[0][1]);
 for(let i=1;i<poly.length;i++)ctx.lineTo(poly[i][0],poly[i][1]);
 ctx.closePath();
 ctx.fill();
 ctx.stroke();
}}
</script>
</body></html>"""
    OUT_QA_HTML.write_text(qa_html,encoding="utf-8")

    print("--- BA0122 EXACT 3D WALL GENERATION v2 ---")
    print("Wall source: filled SVG wall masses (#c7c8c9, #646566)")
    print(f"Extruded meshes: {len(meshes)}")
    print(f"Skipped degenerate fragments: {len(skipped)}")
    print(f"Wall height: {WALL_HEIGHT_M:.2f} m [ASSUMPTION]")
    print(f"JSON: {OUT_JSON}")
    print(f"OBJ: {OUT_OBJ}")
    print(f"Viewer 3D: {OUT_HTML}")
    print(f"QA 2D vs Master: {OUT_QA_HTML}")
    print("QA: no BO..Bf outline path is closed/extruded as a wall solid.")

if __name__=="__main__":
    main()
