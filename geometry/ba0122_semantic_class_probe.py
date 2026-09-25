import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE_PATH = Path("sources/skanska/stilla/BA0122.svg")
OUTPUT_PATH = Path("build/BA0122_semantic_class_probe.json")
HTML_PATH = Path("build/BA0122_semantic_class_probe.html")

def local_name(tag):
    return tag.split("}",1)[-1]

def class_set(el):
    return set(el.attrib.get("class","").split())

def annotate(root):
    idx=0
    for el in root.iter():
        if local_name(el.tag)=="path":
            el.attrib["data-semantic-index"]=str(idx)
            idx+=1
    return idx

def collect(root):
    layers={
        "black_024_no_fill":[],
        "black_any":[],
        "gray_012":[],
        "no_fill_any":[],
        "unclipped_black_024_no_fill":[],
        "clipped_B_black":[],
        "clipped_B_gray":[],
    }
    idx=0
    for el in root.iter():
        if local_name(el.tag)!="path":
            continue
        c=class_set(el)
        if {"H","I","K"}.issubset(c):
            layers["black_024_no_fill"].append(idx)
            if "B" not in c and "F" not in c:
                layers["unclipped_black_024_no_fill"].append(idx)
        if "I" in c:
            layers["black_any"].append(idx)
        if {"G","J"}.issubset(c):
            layers["gray_012"].append(idx)
        if "K" in c:
            layers["no_fill_any"].append(idx)
        if {"B","I"}.issubset(c):
            layers["clipped_B_black"].append(idx)
        if {"B","G"}.issubset(c):
            layers["clipped_B_gray"].append(idx)
        idx+=1
    return layers

def build_html(svg_text,layers):
    root=ET.fromstring(svg_text)
    annotate(root)
    svg=ET.tostring(root,encoding="unicode")
    layers_json=json.dumps(layers,ensure_ascii=False)
    buttons="\n".join(
        f'<button onclick="showLayer(\'{name}\')">{name} ({len(ids)})</button>'
        for name,ids in layers.items()
    )
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>BA0122 semantic class probe</title>
<style>
body{{margin:0;font-family:Arial,sans-serif;background:#eef2f7}}
header{{padding:12px 16px;background:#111827;color:white}}
main{{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px;padding:12px}}
.viewer,.panel{{background:white;border-radius:10px;padding:10px}}
.viewer{{overflow:auto;min-height:82vh}}
button{{display:block;width:100%;margin:5px 0;padding:9px;text-align:left}}
svg{{width:100%;height:auto}}
.hit{{stroke:#ff0000!important;stroke-width:3!important;fill:#ff0000!important;fill-opacity:.12!important;vector-effect:non-scaling-stroke}}
</style>
</head>
<body>
<header><b>BA0122 — semantic CSS probe</b></header>
<main>
<div class="viewer">{svg}</div>
<div class="panel">
<button onclick="clearLayer()">Wyczyść</button>
{buttons}
<hr>
<p>Interpretacja klas z CSS:</p>
<ul>
<li>B/F = clip-path</li>
<li>G = stroke #777</li>
<li>I = stroke #000</li>
<li>H = stroke-width .24</li>
<li>J = stroke-width .12</li>
<li>K = fill:none</li>
</ul>
<p>Najważniejszy test: <b>unclipped_black_024_no_fill</b>.</p>
</div>
</main>
<script>
const layers={layers_json};
function clearLayer(){{document.querySelectorAll('.hit').forEach(x=>x.classList.remove('hit'));}}
function showLayer(name){{
 clearLayer();
 for(const idx of layers[name]||[]){{
   const el=document.querySelector('[data-semantic-index="'+idx+'"]');
   if(el)el.classList.add('hit');
 }}
}}
</script>
</body>
</html>"""

def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Brak {SOURCE_PATH}")
    svg_text=SOURCE_PATH.read_text(encoding="utf-8")
    root=ET.fromstring(svg_text)
    layers=collect(root)
    OUTPUT_PATH.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({k:{"count":len(v),"indices":v} for k,v in layers.items()},ensure_ascii=False,indent=2),encoding="utf-8")
    HTML_PATH.write_text(build_html(svg_text,layers),encoding="utf-8")
    print("--- BA0122 SEMANTIC CSS PROBE ---")
    for name,ids in layers.items():
        print(f"{name}: {len(ids)}")
    print(f"Raport: {OUTPUT_PATH}")
    print(f"Podgląd: {HTML_PATH}")
    print("Najpierw sprawdź: unclipped_black_024_no_fill, potem black_024_no_fill, black_any, gray_012.")

if __name__=="__main__":
    main()
