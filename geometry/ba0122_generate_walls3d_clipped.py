import json
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE=Path("sources/skanska/stilla/BA0122.svg")
OUT=Path("build/BA0122_walls3d_clipped_v3.html")

def lname(tag):
    return tag.split("}",1)[-1]

def serialize(el):
    return ET.tostring(el,encoding="unicode")

def build_wall_svg(root):
    children=list(root)
    # Preserve style, defs and clip paths exactly because class B/F depend on them.
    keep=[]
    for idx,ch in enumerate(children):
        name=lname(ch.tag)
        if idx in (0,1,2,4,5,11,12):  # style, defs, clipPaths, wall-mass groups
            keep.append(serialize(ch))
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 750 563" width="750" height="563">' + ''.join(keep) + '</svg>'

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing {SOURCE}")
    root=ET.parse(SOURCE).getroot()
    wall_svg=build_wall_svg(root)
    wall_svg_json=json.dumps(wall_svg)

    html=f"""<!doctype html>
<html><head><meta charset="utf-8"><title>BA0122 clipped wall masses v3</title>
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;font-family:Arial,sans-serif;background:#eef2f7}}
#view{{position:absolute;inset:0}}
#info{{position:absolute;z-index:5;left:12px;top:12px;background:#fffF;padding:10px;border-radius:8px;box-shadow:0 2px 10px #0002}}
#qa{{position:absolute;right:12px;top:12px;width:300px;background:#fffF;padding:8px;border-radius:8px;z-index:5}}
#mask{{width:100%;height:auto;border:1px solid #ccc;background:white}}
button{{margin:3px;padding:6px 9px}}
</style></head>
<body>
<canvas id="view"></canvas>
<div id="info"><b>BA0122 — ściany 3D v3</b><br>
Źródło: oryginalne grupy ścian + oryginalny clip-path SVG<br>
Plan nie jest rekonstruowany z trójkątów.<br>
<b>Uwaga:</b> przy obrocie 3D prostokąt w rzucie ekranu naturalnie staje się równoległobokiem. Do kontroli geometrii użyj „Rzut 2D 1:1”.<br>
Wysokość: 2.70 m [ASSUMPTION]<br>
<span id="status">Rasteryzacja dokładnego wall-mask…</span><br>
<button onclick="setPlan()">Rzut 2D 1:1</button>
<button onclick="setTop3D()">Widok z góry 3D</button>
<button onclick="setIso()">Widok 3D</button>
</div>
<div id="qa"><b>Dokładny wall-mask 2D</b><canvas id="mask" width="750" height="563"></canvas></div>
<script>
const wallSvg={wall_svg_json};
const SCALE=0.01842931985828394;
const H=2.70;
const view=document.getElementById('view'),ctx=view.getContext('2d');
const mask=document.getElementById('mask'),mctx=mask.getContext('2d');
let rects=[], yaw=-0.75,pitch=0.62,zoom=70,drag=false,lx=0,ly=0,mode='3d';
let bounds=null;

function svgImage(){{
 return new Promise((resolve,reject)=>{{
   const blob=new Blob([wallSvg],{{type:'image/svg+xml'}});
   const url=URL.createObjectURL(blob);
   const img=new Image();
   img.onload=()=>{{URL.revokeObjectURL(url);resolve(img)}};
   img.onerror=e=>reject(e);
   img.src=url;
 }});
}}

function scanRuns(imageData,w,h){{
 const rows=[];
 for(let y=0;y<h;y++){{
   const runs=[];let x=0;
   while(x<w){{
     const a=imageData.data[(y*w+x)*4+3];
     if(a<64){{x++;continue;}}
     const x0=x; while(x<w && imageData.data[(y*w+x)*4+3]>=64)x++;
     runs.push([x0,x]);
   }}
   rows.push(runs);
 }}
 // Merge identical horizontal runs across consecutive rows.
 const active=new Map(), out=[];
 for(let y=0;y<h;y++){{
   const now=new Map();
   for(const [x0,x1] of rows[y]){{
     const key=x0+','+x1;
     if(active.has(key)){{
       const r=active.get(key); r.y1=y+1; now.set(key,r);
     }} else {{
       now.set(key,{{x0,x1,y0:y,y1:y+1}});
     }}
   }}
   for(const [k,r] of active) if(!now.has(k)) out.push(r);
   active.clear(); for(const [k,r] of now) active.set(k,r);
 }}
 for(const r of active.values())out.push(r);
 return out;
}}

function computeBounds(){{
 let minx=Infinity,miny=Infinity,maxx=-Infinity,maxy=-Infinity;
 for(const r of rects){{minx=Math.min(minx,r.x0);maxx=Math.max(maxx,r.x1);miny=Math.min(miny,r.y0);maxy=Math.max(maxy,r.y1);}}
 bounds={{minx:minx*SCALE,maxx:maxx*SCALE,miny:miny*SCALE,maxy:maxy*SCALE}};
}}

function project(p){{
 const cx=(bounds.minx+bounds.maxx)/2, cy=(bounds.miny+bounds.maxy)/2;
 let x=p[0]-cx,y=p[1]-cy,z=p[2]-H/2;
 if(mode==='plan'){{
   return [innerWidth/2+x*zoom,innerHeight/2+y*zoom,z];
 }}
 const ca=Math.cos(yaw),sa=Math.sin(yaw);
 let x1=ca*x-sa*y, y1=sa*x+ca*y;
 const cp=Math.cos(pitch),sp=Math.sin(pitch);
 let y2=cp*y1-sp*z, z2=sp*y1+cp*z;
 return [innerWidth/2+x1*zoom,innerHeight/2+y2*zoom,z2];
}}

function facesForRect(r){{
 const x0=r.x0*SCALE,x1=r.x1*SCALE,y0=r.y0*SCALE,y1=r.y1*SCALE,z0=0,z1=H;
 const v=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]];
 const f=[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]];
 return f.map(ids=>ids.map(i=>v[i]));
}}

function draw(){{
 const dpr=devicePixelRatio||1;view.width=innerWidth*dpr;view.height=innerHeight*dpr;view.style.width=innerWidth+'px';view.style.height=innerHeight+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
 ctx.fillStyle='#f7f7f5';ctx.fillRect(0,0,innerWidth,innerHeight);
 const polys=[];
 for(const r of rects)for(const face of facesForRect(r)){{
   const pp=face.map(project);const depth=pp.reduce((s,p)=>s+p[2],0)/pp.length;polys.push({{p:pp,d:depth}});
 }}
 polys.sort((a,b)=>a.d-b.d);
 for(const q of polys){{ctx.beginPath();ctx.moveTo(q.p[0][0],q.p[0][1]);for(let i=1;i<q.p.length;i++)ctx.lineTo(q.p[i][0],q.p[i][1]);ctx.closePath();ctx.fillStyle='#c9c9c5';ctx.fill();ctx.strokeStyle='#777';ctx.lineWidth=.45;ctx.stroke();}}
}}

function setPlan(){{mode='plan';yaw=0;pitch=0;zoom=Math.min(innerWidth/(bounds.maxx-bounds.minx+1),innerHeight/(bounds.maxy-bounds.miny+1))*.82;draw();}}
function setTop3D(){{mode='3d';yaw=0;pitch=0;zoom=Math.min(innerWidth/(bounds.maxx-bounds.minx+1),innerHeight/(bounds.maxy-bounds.miny+1))*.82;draw();}}
function setIso(){{mode='3d';yaw=-0.75;pitch=0.62;zoom=Math.min(innerWidth,innerHeight)/12;draw();}}

view.addEventListener('mousedown',e=>{{drag=true;lx=e.clientX;ly=e.clientY}});
addEventListener('mouseup',()=>drag=false);
addEventListener('mousemove',e=>{{if(!drag)return;if(mode==='plan'){{lx=e.clientX;ly=e.clientY;return;}}yaw+=(e.clientX-lx)*.008;pitch=Math.max(-1.45,Math.min(1.45,pitch+(e.clientY-ly)*.008));lx=e.clientX;ly=e.clientY;draw();}});
view.addEventListener('wheel',e=>{{e.preventDefault();zoom*=Math.exp(-e.deltaY*.001);draw()}},{{passive:false}});
addEventListener('resize',draw);

(async()=>{{
 try{{
  const img=await svgImage();
  mctx.clearRect(0,0,750,563);mctx.drawImage(img,0,0,750,563);
  const id=mctx.getImageData(0,0,750,563);
  rects=scanRuns(id,750,563);
  computeBounds();setIso();
  document.getElementById('status').textContent='Wall-mask OK · prostokąty: '+rects.length;
 }}catch(e){{document.getElementById('status').textContent='BŁĄD: '+e;console.error(e)}}
}})();
</script>
</body></html>"""
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(html,encoding="utf-8")
    print("--- BA0122 CLIPPED WALL-MASS 3D v3 ---")
    print("Method: browser rasterization of exact source wall groups with clip-path preserved")
    print(f"Viewer: {OUT}")
    print("QA target: 2D wall-mask must visually match original SVG wall thicknesses before 3D acceptance.")

if __name__=="__main__":
    main()
