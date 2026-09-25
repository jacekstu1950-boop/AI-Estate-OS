import json
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE=Path("sources/skanska/stilla/BA0122.svg")
OPENINGS=Path("geometry/master/BA0122.openings.v1.json")
OUT=Path("build/BA0122_openings_v1.html")

SCALE=0.01842931985828394
WALL_H=2.70
DOOR_H=2.10  # ASSUMPTION_CONFIGURABLE
FRAME_W=0.05 # visualization only, not plan geometry truth

def lname(tag):
    return tag.split("}",1)[-1]

def serialize(el):
    return ET.tostring(el,encoding="unicode")

def wall_svg(root):
    children=list(root)
    keep=[]
    for idx,ch in enumerate(children):
        if idx in (0,1,2,4,5,11,12):
            keep.append(serialize(ch))
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 750 563" width="750" height="563">' + ''.join(keep) + '</svg>'

def main():
    root=ET.parse(SOURCE).getroot()
    walls=wall_svg(root)
    ops=json.loads(OPENINGS.read_text(encoding="utf-8"))["openings"]

    payload=json.dumps(ops,ensure_ascii=False)
    wall_json=json.dumps(walls)

    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>BA0122 openings v1</title>
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;font-family:Arial,sans-serif;background:#eef2f7}}
#v{{position:absolute;inset:0}}
#info{{position:absolute;z-index:4;left:12px;top:12px;background:#fffF;padding:10px;border-radius:8px;max-width:480px;box-shadow:0 2px 10px #0002}}
#legend{{position:absolute;z-index:4;right:12px;top:12px;background:#fffF;padding:10px;border-radius:8px;max-width:350px}}
button{{margin:3px;padding:6px 9px}}
</style></head><body>
<canvas id="v"></canvas>
<div id="info"><b>BA0122 — openings integration v1</b><br>
Ściany: zaakceptowany wall-mask z clip-path.<br>
Otwory: 5 pozycji z BA0122.openings.v1.json.<br>
Drzwi: wysokość 2.10 m = <b>ASSUMPTION_CONFIGURABLE</b>.<br>
Balkon: szerokości całkowite SOURCE-DERIVED; podział skrzydło/szklenie nadal PENDING.<br>
<button onclick="setTop()">Rzut z góry</button><button onclick="setIso()">3D</button><button onclick="set90()">90°</button>
<div id="status">Ładowanie…</div></div>
<div id="legend"><b>Kontrola otworów</b><div id="list"></div></div>
<script>
const wallSvg={wall_json};
const openings={payload};
const SCALE={SCALE}, H={WALL_H}, DOOR_H={DOOR_H};
const canvas=document.getElementById('v'),ctx=canvas.getContext('2d');
let rects=[],bounds=null,yaw=-.75,pitch=.58,zoom=70,drag=false,lx=0,ly=0,mode='affine';

function svgImage(){{return new Promise((resolve,reject)=>{{const b=new Blob([wallSvg],{{type:'image/svg+xml'}}),u=URL.createObjectURL(b),i=new Image();i.onload=()=>{{URL.revokeObjectURL(u);resolve(i)}};i.onerror=reject;i.src=u}})}}
function scanRuns(id,w,h){{const rows=[];for(let y=0;y<h;y++){{const runs=[];let x=0;while(x<w){{if(id.data[(y*w+x)*4+3]<64){{x++;continue}}const x0=x;while(x<w&&id.data[(y*w+x)*4+3]>=64)x++;runs.push([x0,x])}}rows.push(runs)}}const active=new Map(),out=[];for(let y=0;y<h;y++){{const now=new Map();for(const [x0,x1] of rows[y]){{const k=x0+','+x1;if(active.has(k)){{const r=active.get(k);r.y1=y+1;now.set(k,r)}}else now.set(k,{{x0,x1,y0:y,y1:y+1}})}}for(const [k,r] of active)if(!now.has(k))out.push(r);active.clear();for(const [k,r] of now)active.set(k,r)}}for(const r of active.values())out.push(r);return out}}
function computeBounds(){{let a=[Infinity,Infinity,-Infinity,-Infinity];for(const r of rects){{a[0]=Math.min(a[0],r.x0);a[1]=Math.min(a[1],r.y0);a[2]=Math.max(a[2],r.x1);a[3]=Math.max(a[3],r.y1)}}bounds={{minx:a[0]*SCALE,miny:a[1]*SCALE,maxx:a[2]*SCALE,maxy:a[3]*SCALE}}}}
function project(p){{const cx=(bounds.minx+bounds.maxx)/2,cy=(bounds.miny+bounds.maxy)/2;let x=p[0]-cx,y=p[1]-cy,z=p[2]-H/2;if(mode==='top')return [innerWidth/2+x*zoom,innerHeight/2+y*zoom,z];const ca=Math.cos(yaw),sa=Math.sin(yaw),xr=ca*x-sa*y,yr=sa*x+ca*y;return [innerWidth/2+xr*zoom,innerHeight/2+yr*zoom*.58-z*zoom*.82,yr]}}
function boxFaces(x0,x1,y0,y1,z0,z1){{const v=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]];return [[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]].map(f=>f.map(i=>v[i]))}}
function wallFaces(r){{return boxFaces(r.x0*SCALE,r.x1*SCALE,r.y0*SCALE,r.y1*SCALE,0,H)}}
function openingPrisms(o){{
 const span=o.span_svg.map(v=>v*SCALE), t=.12, parts=[];
 if(o.wall_axis==='horizontal'){{
   const y=o.wall_y_svg*SCALE;
   if(o.type==='door') parts.push(...boxFaces(span[0],span[1],y-t/2,y+t/2,DOOR_H,H));
   else {{
     // balcony assembly: frame only, no invented internal split
     const fw=.05;
     parts.push(...boxFaces(span[0],span[0]+fw,y-t/2,y+t/2,0,H));
     parts.push(...boxFaces(span[1]-fw,span[1],y-t/2,y+t/2,0,H));
     parts.push(...boxFaces(span[0],span[1],y-t/2,y+t/2,H-fw,H));
   }}
 }} else {{
   const x=o.wall_x_svg*SCALE;
   if(o.type==='door') parts.push(...boxFaces(x-t/2,x+t/2,span[0],span[1],DOOR_H,H));
 }}
 return parts;
}}
function draw(){{const dpr=devicePixelRatio||1;canvas.width=innerWidth*dpr;canvas.height=innerHeight*dpr;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#f7f7f5';ctx.fillRect(0,0,innerWidth,innerHeight);const polys=[];for(const r of rects)for(const f of wallFaces(r)){{const p=f.map(project);polys.push({{p,d:p.reduce((s,q)=>s+q[2],0)/p.length,c:'#c9c9c5'}})}}for(const o of openings)for(const f of openingPrisms(o)){{const p=f.map(project);polys.push({{p,d:p.reduce((s,q)=>s+q[2],0)/p.length,c:o.type==='door'?'#9b7653':'#86a9c4'}})}}polys.sort((a,b)=>a.d-b.d);for(const q of polys){{ctx.beginPath();ctx.moveTo(q.p[0][0],q.p[0][1]);for(let i=1;i<q.p.length;i++)ctx.lineTo(q.p[i][0],q.p[i][1]);ctx.closePath();ctx.fillStyle=q.c;ctx.fill();ctx.strokeStyle='#555';ctx.lineWidth=.45;ctx.stroke()}}}}
function setTop(){{mode='top';zoom=Math.min(innerWidth/(bounds.maxx-bounds.minx+1),innerHeight/(bounds.maxy-bounds.miny+1))*.82;draw()}}
function setIso(){{mode='affine';yaw=-.75;zoom=Math.min(innerWidth,innerHeight)/12;draw()}}
function set90(){{mode='affine';yaw=Math.PI/2;zoom=Math.min(innerWidth,innerHeight)/12;draw()}}
canvas.addEventListener('mousedown',e=>{{drag=true;lx=e.clientX;ly=e.clientY}});addEventListener('mouseup',()=>drag=false);addEventListener('mousemove',e=>{{if(!drag||mode==='top')return;yaw+=(e.clientX-lx)*.008;lx=e.clientX;ly=e.clientY;draw()}});canvas.addEventListener('wheel',e=>{{e.preventDefault();zoom*=Math.exp(-e.deltaY*.001);draw()}},{{passive:false}});addEventListener('resize',draw);
(async()=>{{try{{const img=await svgImage(),tmp=document.createElement('canvas');tmp.width=750;tmp.height=563;const t=tmp.getContext('2d');t.drawImage(img,0,0,750,563);rects=scanRuns(t.getImageData(0,0,750,563),750,563);computeBounds();setIso();document.getElementById('status').textContent='Wall-mask + openings załadowane';document.getElementById('list').innerHTML=openings.map(o=>'<p><b>'+o.id+'</b><br>'+o.width_m.toFixed(3)+' m · '+o.qa+'</p>').join('')}}catch(e){{document.getElementById('status').textContent='BŁĄD: '+e;console.error(e)}}}})();
</script></body></html>"""
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(html,encoding="utf-8")
    print("--- BA0122 OPENINGS INTEGRATION v1 ---")
    print("Walls: ACCEPTED clipped wall mask")
    print("Openings: 5 source-derived positions")
    print(f"Door height: {DOOR_H:.2f} m [ASSUMPTION_CONFIGURABLE]")
    print("Balcony assembly subpanel split: PENDING")
    print(f"Viewer: {OUT}")

if __name__=="__main__":
    main()
