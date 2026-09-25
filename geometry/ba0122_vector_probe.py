import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_PATH = Path("sources/skanska/stilla/BA0122.svg")
OUTPUT_PATH = Path("build/BA0122_vector_probe.json")
HTML_PATH = Path("build/BA0122_vector_probe.html")

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


def merged_style(element, css_classes):
    style = {}
    cls = element.attrib.get("class", "")
    for name in cls.split():
        style.update(css_classes.get(name, {}))
    style.update(parse_style_attr(element.attrib.get("style", "")))
    for key in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity"):
        if key in element.attrib:
            style[key] = element.attrib[key]
    return style


def parse_css_classes(root):
    classes = {}
    for element in root.iter():
        if local_name(element.tag) != "style" or not element.text:
            continue
        css = element.text
        for selector, body in re.findall(r"\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}", css, re.S):
            classes[selector] = parse_style_attr(body)
    return classes


def path_command_counts(d):
    return Counter(re.findall(r"[A-Za-z]", d or ""))


def extract_numbers(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text or "")]


def rough_path_bbox(d):
    nums = extract_numbers(d)
    if len(nums) < 2:
        return None
    pairs = list(zip(nums[0::2], nums[1::2]))
    if not pairs:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_area(bbox):
    if not bbox:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def normalized_color(value):
    if value is None:
        return None
    return value.strip().lower()


def classify_path(style, bbox, d):
    fill = normalized_color(style.get("fill"))
    stroke = normalized_color(style.get("stroke"))
    stroke_width = style.get("stroke-width")
    area = bbox_area(bbox)
    commands = path_command_counts(d)

    reasons = []
    score = 0

    if stroke and stroke not in ("none", "transparent"):
        score += 2
        reasons.append("has_stroke")

    try:
        sw = float(stroke_width) if stroke_width is not None else 0.0
    except ValueError:
        sw = 0.0
    if sw >= 1.0:
        score += 2
        reasons.append("stroke_width>=1")

    if fill in ("none", "transparent"):
        score += 1
        reasons.append("no_fill")

    if area >= 5000:
        score += 2
        reasons.append("large_bbox")
    elif area >= 1000:
        score += 1
        reasons.append("medium_bbox")

    if commands.get("L", 0) + commands.get("l", 0) >= 2:
        score += 1
        reasons.append("line_rich")

    if commands.get("C", 0) + commands.get("c", 0) > 5 and area < 2000:
        score -= 2
        reasons.append("curve_dense_small")

    if area < 50:
        score -= 2
        reasons.append("tiny_bbox")

    return {
        "score": score,
        "candidate": score >= 3,
        "reasons": reasons,
    }


def element_ref(element):
    return element.attrib.get("href") or element.attrib.get(XLINK)


def build_report(root):
    css_classes = parse_css_classes(root)
    ids = {}
    groups = []
    paths = []
    uses = []
    style_counter = Counter()
    class_counter = Counter()

    for element in root.iter():
        element_id = element.attrib.get("id")
        if element_id:
            ids[element_id] = local_name(element.tag)

    for element in root.iter():
        name = local_name(element.tag)
        if name == "g":
            groups.append({
                "id": element.attrib.get("id"),
                "class": element.attrib.get("class"),
                "transform": element.attrib.get("transform"),
                "children": len(list(element)),
            })
        elif name == "use":
            uses.append({
                "id": element.attrib.get("id"),
                "ref": element_ref(element),
                "x": element.attrib.get("x"),
                "y": element.attrib.get("y"),
                "transform": element.attrib.get("transform"),
                "class": element.attrib.get("class"),
            })
        elif name == "path":
            style = merged_style(element, css_classes)
            bbox = rough_path_bbox(element.attrib.get("d", ""))
            classification = classify_path(style, bbox, element.attrib.get("d", ""))
            class_counter[element.attrib.get("class", "")] += 1
            style_key = json.dumps(style, sort_keys=True, ensure_ascii=False)
            style_counter[style_key] += 1
            paths.append({
                "id": element.attrib.get("id"),
                "class": element.attrib.get("class"),
                "style": style,
                "bbox_rough": bbox,
                "bbox_area_rough": round(bbox_area(bbox), 3),
                "commands": dict(path_command_counts(element.attrib.get("d", ""))),
                "classification": classification,
            })

    candidates = [p for p in paths if p["classification"]["candidate"]]
    candidates.sort(key=lambda p: (p["classification"]["score"], p["bbox_area_rough"]), reverse=True)

    return {
        "viewBox": root.attrib.get("viewBox"),
        "width": root.attrib.get("width"),
        "height": root.attrib.get("height"),
        "css_class_count": len(css_classes),
        "css_classes": css_classes,
        "id_count": len(ids),
        "groups_count": len(groups),
        "uses_count": len(uses),
        "paths_count": len(paths),
        "candidate_paths_count": len(candidates),
        "top_classes": class_counter.most_common(30),
        "top_styles": style_counter.most_common(30),
        "groups": groups,
        "uses_sample": uses[:100],
        "candidate_paths_top": candidates[:200],
    }


def build_html(svg_text, report):
    candidate_ids = [p["id"] for p in report["candidate_paths_top"] if p.get("id")]
    ids_json = json.dumps(candidate_ids, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>BA0122 vector probe</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#f3f4f6; }}
header {{ padding:12px 16px; background:#111827; color:white; }}
main {{ display:grid; grid-template-columns: 1fr 340px; gap:12px; padding:12px; }}
.viewer {{ background:white; border-radius:10px; padding:10px; min-height:80vh; overflow:auto; }}
.panel {{ background:white; border-radius:10px; padding:12px; }}
svg {{ width:100%; height:auto; }}
.highlight {{ stroke:#ff0000 !important; stroke-width:2.5 !important; fill-opacity:.15 !important; }}
button {{ margin:4px 0; padding:8px 10px; }}
code {{ word-break:break-all; }}
</style>
</head>
<body>
<header><b>BA0122 — vector probe</b> · czerwone = kandydaci ścian/konturów</header>
<main>
<div class="viewer" id="viewer">{svg_text}</div>
<div class="panel">
<p><b>paths:</b> {report['paths_count']}</p>
<p><b>uses:</b> {report['uses_count']}</p>
<p><b>groups:</b> {report['groups_count']}</p>
<p><b>kandydaci:</b> {report['candidate_paths_count']}</p>
<button onclick="highlight()">Podświetl kandydatów</button>
<button onclick="clearHighlight()">Usuń podświetlenie</button>
<p>Ten widok nie zmienia SVG. Służy tylko do inspekcji przed budową Master Geometry.</p>
</div>
</main>
<script>
const candidateIds = {ids_json};
function highlight() {{
  for (const id of candidateIds) {{
    const el = document.getElementById(id);
    if (el) el.classList.add('highlight');
  }}
}}
function clearHighlight() {{
  document.querySelectorAll('.highlight').forEach(x => x.classList.remove('highlight'));
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
    root = ET.fromstring(svg_text)
    report = build_report(root)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    HTML_PATH.write_text(build_html(svg_text, report), encoding="utf-8")

    print("--- BA0122 VECTOR PROBE ---")
    print(f"viewBox: {report['viewBox']}")
    print(f"paths: {report['paths_count']}")
    print(f"uses: {report['uses_count']}")
    print(f"groups: {report['groups_count']}")
    print(f"candidate paths: {report['candidate_paths_count']}")
    print("Top classes:")
    for name, count in report["top_classes"][:10]:
        print(f"  {name or '(brak klasy)'}: {count}")
    print("Top styles:")
    for style, count in report["top_styles"][:10]:
        print(f"  {count} × {style}")
    print(f"Raport: {OUTPUT_PATH}")
    print(f"Podgląd: {HTML_PATH}")
    print("Otwórz HTML i kliknij 'Podświetl kandydatów'.")


if __name__ == "__main__":
    main()
