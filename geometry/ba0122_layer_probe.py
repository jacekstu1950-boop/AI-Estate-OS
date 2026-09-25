import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SOURCE_PATH = Path("sources/skanska/stilla/BA0122.svg")
OUTPUT_PATH = Path("build/BA0122_layer_probe.json")
HTML_PATH = Path("build/BA0122_layer_probe.html")

XLINK = "{http://www.w3.org/1999/xlink}href"


def local_name(tag):
    return tag.split("}", 1)[-1]


def parse_style_attr(style):
    result = {}
    for part in (style or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_css_classes(root):
    classes = {}
    for element in root.iter():
        if local_name(element.tag) != "style" or not element.text:
            continue
        css = element.text
        for selector, body in re.findall(r"\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}", css, re.S):
            classes[selector] = parse_style_attr(body)
    return classes


def merged_style(element, css_classes):
    style = {}
    for cls in element.attrib.get("class", "").split():
        style.update(css_classes.get(cls, {}))
    style.update(parse_style_attr(element.attrib.get("style", "")))
    for key in (
        "fill", "stroke", "stroke-width", "opacity",
        "fill-opacity", "stroke-opacity", "clip-path"
    ):
        if key in element.attrib:
            style[key] = element.attrib[key]
    return style


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
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def path_commands(d):
    return Counter(re.findall(r"[A-Za-z]", d or ""))


def make_record(element, css_classes, index):
    style = merged_style(element, css_classes)
    bbox = rough_bbox(element.attrib.get("d", ""))
    commands = path_commands(element.attrib.get("d", ""))
    cls = element.attrib.get("class", "")
    stroke = style.get("stroke")
    fill = style.get("fill")
    clip = style.get("clip-path")

    return {
        "index": index,
        "id": element.attrib.get("id"),
        "class": cls,
        "clip_path": clip,
        "stroke": stroke,
        "stroke_width": style.get("stroke-width"),
        "fill": fill,
        "bbox": bbox,
        "bbox_area": round(bbox_area(bbox), 3),
        "commands": dict(commands),
        "d": element.attrib.get("d", ""),
    }


def classify(records):
    layers = {
        "class_B": [],
        "class_F": [],
        "no_class": [],
        "stroked": [],
        "large": [],
        "very_large": [],
        "clip_Bz": [],
        "clip_Bx": [],
        "line_rich": [],
        "curve_dense": [],
    }

    for rec in records:
        classes = set(rec["class"].split())
        if "B" in classes:
            layers["class_B"].append(rec["index"])
        if "F" in classes:
            layers["class_F"].append(rec["index"])
        if not rec["class"]:
            layers["no_class"].append(rec["index"])
        if rec["stroke"] and rec["stroke"].lower() not in ("none", "transparent"):
            layers["stroked"].append(rec["index"])
        if rec["bbox_area"] >= 1000:
            layers["large"].append(rec["index"])
        if rec["bbox_area"] >= 10000:
            layers["very_large"].append(rec["index"])
        if rec["clip_path"] == "url(#Bz)":
            layers["clip_Bz"].append(rec["index"])
        if rec["clip_path"] == "url(#Bx)":
            layers["clip_Bx"].append(rec["index"])

        cmds = rec["commands"]
        line_count = cmds.get("L", 0) + cmds.get("l", 0) + cmds.get("H", 0) + cmds.get("h", 0) + cmds.get("V", 0) + cmds.get("v", 0)
        curve_count = cmds.get("C", 0) + cmds.get("c", 0) + cmds.get("Q", 0) + cmds.get("q", 0) + cmds.get("A", 0) + cmds.get("a", 0)
        if line_count >= 3 and curve_count <= 2:
            layers["line_rich"].append(rec["index"])
        if curve_count >= 6:
            layers["curve_dense"].append(rec["index"])

    return layers


def ensure_probe_ids(svg_text):
    root = ET.fromstring(svg_text)
    counter = 0
    for element in root.iter():
        if local_name(element.tag) != "path":
            continue
        if "id" not in element.attrib:
            element.attrib["id"] = f"probe-path-{counter}"
        element.attrib["data-probe-index"] = str(counter)
        counter += 1
    return ET.tostring(root, encoding="unicode")


def build_report(svg_text):
    root = ET.fromstring(svg_text)
    css_classes = parse_css_classes(root)

    records = []
    i = 0
    for element in root.iter():
        if local_name(element.tag) != "path":
            continue
        records.append(make_record(element, css_classes, i))
        i += 1

    layers = classify(records)
    return {
        "viewBox": root.attrib.get("viewBox"),
        "paths_count": len(records),
        "css_classes": css_classes,
        "layer_counts": {name: len(indexes) for name, indexes in layers.items()},
        "layers": layers,
        "records_sample": records[:250],
    }


def build_html(svg_text, report):
    probe_svg = ensure_probe_ids(svg_text)
    layers_json = json.dumps(report["layers"], ensure_ascii=False)
    counts = report["layer_counts"]

    buttons = "\n".join(
        f'<button onclick="showLayer(\'{name}\')">{name} ({count})</button>'
        for name, count in counts.items()
    )

    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>BA0122 layer probe</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#eef2f7; }}
header {{ padding:12px 16px; background:#111827; color:#fff; }}
main {{ display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:12px; padding:12px; }}
.viewer {{ background:#fff; border-radius:10px; padding:10px; overflow:auto; min-height:82vh; }}
.panel {{ background:#fff; border-radius:10px; padding:12px; }}
button {{ display:block; width:100%; margin:5px 0; padding:9px; text-align:left; }}
svg {{ width:100%; height:auto; }}
.probe-hit {{
  stroke:#ff0000 !important;
  stroke-width:2.8 !important;
  fill:#ff0000 !important;
  fill-opacity:.16 !important;
  vector-effect:non-scaling-stroke;
}}
</style>
</head>
<body>
<header><b>BA0122 — layer probe</b> · wybierz jedną warstwę i sprawdź, co podświetla</header>
<main>
<div class="viewer">{probe_svg}</div>
<div class="panel">
<button onclick="clearLayer()">Wyczyść</button>
{buttons}
<hr>
<p><b>Cel:</b> znaleźć zestaw ścieżek odpowiadający ścianom / obrysowi, a odrzucić meble, symbole i grafikę.</p>
<p>Najbardziej interesujące na start: <b>stroked</b>, <b>very_large</b>, <b>line_rich</b>, <b>class_B</b>, <b>class_F</b>.</p>
<p>Po kliknięciu proszę zanotować, która warstwa najbardziej przypomina ściany.</p>
</div>
</main>
<script>
const layers = {layers_json};

function clearLayer() {{
  document.querySelectorAll('.probe-hit').forEach(el => el.classList.remove('probe-hit'));
}}

function showLayer(name) {{
  clearLayer();
  for (const idx of layers[name] || []) {{
    const el = document.querySelector('[data-probe-index="' + idx + '"]');
    if (el) el.classList.add('probe-hit');
  }}
}}
</script>
</body>
</html>"""


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Brak {SOURCE_PATH}. Uruchom najpierw: python -m geometry.ba0122_source_audit"
        )

    svg_text = SOURCE_PATH.read_text(encoding="utf-8")
    report = build_report(svg_text)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    HTML_PATH.write_text(build_html(svg_text, report), encoding="utf-8")

    print("--- BA0122 LAYER PROBE ---")
    print(f"viewBox: {report['viewBox']}")
    print(f"paths: {report['paths_count']}")
    for name, count in report["layer_counts"].items():
        print(f"{name}: {count}")
    print(f"Raport: {OUTPUT_PATH}")
    print(f"Podgląd: {HTML_PATH}")
    print("Otwórz HTML i sprawdź kolejno: stroked, very_large, line_rich, class_B, class_F.")


if __name__ == "__main__":
    main()
