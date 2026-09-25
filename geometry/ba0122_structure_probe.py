import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SOURCE_PATH = Path("sources/skanska/stilla/BA0122.svg")
OUTPUT_PATH = Path("build/BA0122_structure_probe.json")
HTML_PATH = Path("build/BA0122_structure_probe.html")

XLINK = "{http://www.w3.org/1999/xlink}href"


def local_name(tag):
    return tag.split("}", 1)[-1]


def extract_numbers(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text or "")]


def rough_bbox(d):
    nums = extract_numbers(d)
    if len(nums) < 4:
        return None
    pairs = list(zip(nums[0::2], nums[1::2]))
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_area(bbox):
    if not bbox:
        return 0.0
    return max(0.0, bbox[2]-bbox[0]) * max(0.0, bbox[3]-bbox[1])


def command_counts(d):
    return Counter(re.findall(r"[A-Za-z]", d or ""))


def referenced_ids(root):
    refs = set()
    for element in root.iter():
        if local_name(element.tag) != "use":
            continue
        href = element.attrib.get("href") or element.attrib.get(XLINK)
        if href and href.startswith("#"):
            refs.add(href[1:])
    return refs


def walk(element, ancestors, records, refs):
    name = local_name(element.tag)
    next_ancestors = ancestors + [name]

    if name == "path":
        path_id = element.attrib.get("id")
        d = element.attrib.get("d", "")
        bbox = rough_bbox(d)
        commands = command_counts(d)
        in_defs = "defs" in ancestors
        in_clip = "clipPath" in ancestors
        rec = {
            "index": len(records),
            "id": path_id,
            "class": element.attrib.get("class", ""),
            "in_defs": in_defs,
            "in_clipPath": in_clip,
            "referenced_by_use": bool(path_id and path_id in refs),
            "bbox": bbox,
            "bbox_area": round(bbox_area(bbox), 3),
            "commands": dict(commands),
        }
        records.append(rec)

    for child in list(element):
        walk(child, next_ancestors, records, refs)


def classify(records):
    layers = {
        "direct_render_paths": [],
        "defs_paths": [],
        "clip_paths": [],
        "referenced_by_use": [],
        "direct_unreferenced": [],
        "direct_large": [],
        "direct_very_large": [],
        "direct_line_rich": [],
        "direct_curve_rich": [],
    }

    for r in records:
        i = r["index"]
        if r["in_defs"]:
            layers["defs_paths"].append(i)
        if r["in_clipPath"]:
            layers["clip_paths"].append(i)
        if r["referenced_by_use"]:
            layers["referenced_by_use"].append(i)

        direct = not r["in_defs"] and not r["in_clipPath"]
        if direct:
            layers["direct_render_paths"].append(i)
            if not r["referenced_by_use"]:
                layers["direct_unreferenced"].append(i)
            if r["bbox_area"] >= 1000:
                layers["direct_large"].append(i)
            if r["bbox_area"] >= 10000:
                layers["direct_very_large"].append(i)

            cmds = r["commands"]
            line_count = sum(cmds.get(k, 0) for k in ("L","l","H","h","V","v"))
            curve_count = sum(cmds.get(k, 0) for k in ("C","c","Q","q","A","a"))
            if line_count >= 3 and curve_count <= 2:
                layers["direct_line_rich"].append(i)
            if curve_count >= 6:
                layers["direct_curve_rich"].append(i)

    return layers


def annotate_paths(root):
    counter = 0
    def rec(el, ancestors):
        nonlocal counter
        name = local_name(el.tag)
        if name == "path":
            el.attrib["data-structure-index"] = str(counter)
            counter += 1
        for child in list(el):
            rec(child, ancestors + [name])
    rec(root, [])
    return root


def build_report(svg_text):
    root = ET.fromstring(svg_text)
    refs = referenced_ids(root)
    records = []
    walk(root, [], records, refs)
    layers = classify(records)
    return {
        "viewBox": root.attrib.get("viewBox"),
        "paths_count": len(records),
        "use_referenced_id_count": len(refs),
        "layer_counts": {k: len(v) for k,v in layers.items()},
        "layers": layers,
        "records_sample": records[:300],
    }


def build_html(svg_text, report):
    root = ET.fromstring(svg_text)
    annotate_paths(root)
    svg = ET.tostring(root, encoding="unicode")
    layers_json = json.dumps(report["layers"], ensure_ascii=False)

    buttons = "\n".join(
        f'<button onclick="showLayer(\'{name}\')">{name} ({count})</button>'
        for name, count in report["layer_counts"].items()
    )

    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>BA0122 structure probe</title>
<style>
body {{margin:0;font-family:Arial,sans-serif;background:#eef2f7}}
header {{padding:12px 16px;background:#111827;color:#fff}}
main {{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px;padding:12px}}
.viewer,.panel {{background:#fff;border-radius:10px;padding:10px}}
.viewer {{overflow:auto;min-height:82vh}}
button {{display:block;width:100%;margin:5px 0;padding:9px;text-align:left}}
svg {{width:100%;height:auto}}
.hit {{
 stroke:#ff0000 !important;
 stroke-width:2.5 !important;
 fill:#ff0000 !important;
 fill-opacity:.18 !important;
 vector-effect:non-scaling-stroke
}}
</style>
</head>
<body>
<header><b>BA0122 — structure probe</b> · rozdzielenie tekstu/glyphów od geometrii</header>
<main>
<div class="viewer">{svg}</div>
<div class="panel">
<button onclick="clearLayer()">Wyczyść</button>
{buttons}
<hr>
<p><b>Najważniejsze:</b> tekst w tym SVG jest najpewniej budowany przez <code>&lt;use&gt;</code> odwołujące się do ścieżek w <code>&lt;defs&gt;</code>.</p>
<p>Dlatego ścian szukamy przede wszystkim w:</p>
<ol>
<li><b>direct_render_paths</b></li>
<li><b>direct_unreferenced</b></li>
<li><b>direct_large</b></li>
<li><b>direct_line_rich</b></li>
</ol>
<p>Warstwy <b>defs_paths</b> i <b>referenced_by_use</b> powinny odpowiadać głównie glifom/napisom i symbolom.</p>
</div>
</main>
<script>
const layers = {layers_json};
function clearLayer() {{
  document.querySelectorAll('.hit').forEach(x=>x.classList.remove('hit'));
}}
function showLayer(name) {{
  clearLayer();
  for (const idx of layers[name] || []) {{
    const el = document.querySelector('[data-structure-index="'+idx+'"]');
    if (el) el.classList.add('hit');
  }}
}}
</script>
</body>
</html>"""


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Brak {SOURCE_PATH}. Najpierw uruchom: python -m geometry.ba0122_source_audit"
        )
    svg_text = SOURCE_PATH.read_text(encoding="utf-8")
    report = build_report(svg_text)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    HTML_PATH.write_text(build_html(svg_text, report), encoding="utf-8")

    print("--- BA0122 STRUCTURE PROBE ---")
    print(f"viewBox: {report['viewBox']}")
    print(f"paths: {report['paths_count']}")
    print(f"use-referenced ids: {report['use_referenced_id_count']}")
    for name,count in report["layer_counts"].items():
        print(f"{name}: {count}")
    print(f"Raport: {OUTPUT_PATH}")
    print(f"Podgląd: {HTML_PATH}")
    print("Sprawdź kolejno: direct_render_paths, direct_unreferenced, direct_large, direct_line_rich.")


if __name__ == "__main__":
    main()
