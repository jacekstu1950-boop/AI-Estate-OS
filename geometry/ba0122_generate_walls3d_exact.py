import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("sources/skanska/stilla/BA0122.svg")
OUT_JSON = Path("build/BA0122_walls3d_exact_v2.json")
OUT_OBJ = Path("build/BA0122_walls3d_exact_v2.obj")
OUT_HTML = Path("build/BA0122_walls3d_exact_v2.html")

SCALE_M = 0.01842931985828394
WALL_HEIGHT_M = 2.70  # configurable assumption; not encoded in 2D SVG

WALL_FILL_COLORS = {"#c7c8c9", "#646566"}

def local_name(tag):
    return tag.split("}", 1)[-1]

def tokenize_path(d):
    return re.findall(r"[MLHVZmlhvz]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", d or "")

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
    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>BA0122 exact walls v2</title>
<style>html,body,#c{{width:100%;height:100%;margin:0;overflow:hidden}}#info{{position:absolute;z-index:2;left:12px;top:12px;background:#fffE;padding:10px;border-radius:8px;font:14px Arial;max-width:420px}}</style>
</head><body><div id="info"><b>BA0122 — EXACT ściany 3D v2</b><br>Źródło: wypełnione masy ścian z SVG<br>Obrysy liniowe BO…Bf: NIE są już ekstrudowane<br>Wysokość 2.70 m: ASSUMPTION<br><span id="status">Ładowanie…</span></div><div id="c"></div>
<script type="importmap">{{{{"imports":{{{{"three":"https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/"}}}}}}}}</script>
<script type="module">
import * as THREE from 'three';
import {{OrbitControls}} from 'three/addons/controls/OrbitControls.js';
const data={payload};
const scene=new THREE.Scene(); scene.background=new THREE.Color(0xf7f7f5);
const camera=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,.01,200);
const renderer=new THREE.WebGLRenderer({{antialias:true}}); renderer.setSize(innerWidth,innerHeight); document.getElementById('c').appendChild(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x777777,2.0));
const sun=new THREE.DirectionalLight(0xffffff,2);sun.position.set(5,10,8);scene.add(sun);
const mat=new THREE.MeshStandardMaterial({{color:0xd9d7d2,roughness:.9,side:THREE.DoubleSide}});
const root=new THREE.Group();scene.add(root);
for(const m of data){{const pos=[];for(const v of m.vertices)pos.push(v[0],v[2],-v[1]);const idx=[];for(const f of m.faces)idx.push(f[0],f[1],f[2]);const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setIndex(idx);g.computeVertexNormals();root.add(new THREE.Mesh(g,mat));}}
const box=new THREE.Box3().setFromObject(root),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),r=Math.max(size.x,size.y,size.z);
controls.target.copy(center);camera.position.set(center.x+r*1.25,center.y+r*1.15,center.z+r*1.25);camera.far=r*20;camera.updateProjectionMatrix();controls.update();
const grid=new THREE.GridHelper(Math.max(14,r*2.2),28,0x999999,0xdddddd);grid.position.y=box.min.y;scene.add(grid);
document.getElementById('status').textContent='Model załadowany. Obrót: mysz, zoom: rolka.';
function anim(){{requestAnimationFrame(anim);controls.update();renderer.render(scene,camera)}}anim();
addEventListener('resize',()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)}})
</script></body></html>"""
    OUT_HTML.write_text(html,encoding="utf-8")

    print("--- BA0122 EXACT 3D WALL GENERATION v2 ---")
    print("Wall source: filled SVG wall masses (#c7c8c9, #646566)")
    print(f"Extruded meshes: {len(meshes)}")
    print(f"Skipped degenerate fragments: {len(skipped)}")
    print(f"Wall height: {WALL_HEIGHT_M:.2f} m [ASSUMPTION]")
    print(f"JSON: {OUT_JSON}")
    print(f"OBJ: {OUT_OBJ}")
    print(f"Viewer: {OUT_HTML}")
    print("QA: no BO..Bf outline path is closed/extruded as a wall solid.")

if __name__=="__main__":
    main()
