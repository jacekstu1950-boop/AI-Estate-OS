import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE_URL = "https://mieszkaj.skanska.pl/app/uploads/crm-images/ST/BA0122.svg"
SOURCE_PATH = Path("sources/skanska/stilla/BA0122.svg")
MASTER_PATH = Path("geometry/master/BA0122.master.json")
INSPECTION_PATH = Path("build/BA0122_source_inspection.json")

SVG_NS = "{http://www.w3.org/2000/svg}"


def download_source():
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "AI-Estate-OS/1.0 BA0122 geometry audit"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload.lstrip().startswith(b"<"):
        raise RuntimeError("Downloaded BA0122 source is not XML/SVG.")
    SOURCE_PATH.write_bytes(payload)
    return payload


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def parse_number(value):
    if value is None:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    return float(match.group(0).replace(",", ".")) if match else None


def local_name(tag):
    return tag.split("}", 1)[-1]


def visible_text(root):
    values = []
    for element in root.iter():
        if element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def primitive_summary(root):
    counts = {}
    primitives = []
    selected = {"path", "rect", "line", "polyline", "polygon", "circle", "ellipse", "text", "image"}
    for element in root.iter():
        name = local_name(element.tag)
        counts[name] = counts.get(name, 0) + 1
        if name in selected:
            item = {"type": name}
            for key in ("id", "x", "y", "x1", "y1", "x2", "y2", "width", "height", "cx", "cy", "r", "d", "points", "transform"):
                if key in element.attrib:
                    item[key] = element.attrib[key]
            if element.text and element.text.strip():
                item["text"] = element.text.strip()
            primitives.append(item)
    return counts, primitives


def extract_area_like_text(texts):
    matches = []
    for text in texts:
        normalized = text.replace(",", ".")
        if re.search(r"\d+(?:\.\d+)?\s*m(?:²|2)", normalized, re.I):
            matches.append(text)
    return matches


def inspect_svg(payload):
    root = ET.fromstring(payload)
    counts, primitives = primitive_summary(root)
    texts = visible_text(root)
    return {
        "source_url": SOURCE_URL,
        "source_file": str(SOURCE_PATH),
        "sha256": sha256_bytes(payload),
        "root_tag": local_name(root.tag),
        "width": root.attrib.get("width"),
        "height": root.attrib.get("height"),
        "viewBox": root.attrib.get("viewBox"),
        "element_counts": counts,
        "text_values": texts,
        "area_like_text": extract_area_like_text(texts),
        "primitive_count": len(primitives),
        "primitives": primitives,
    }


def update_master(inspection):
    master = json.loads(MASTER_PATH.read_text(encoding="utf-8"))
    master["source_status"] = "DOWNLOADED_OFFICIAL_SOURCE"
    master["source_sha256"] = inspection["sha256"]
    master["svg_width"] = inspection["width"]
    master["svg_height"] = inspection["height"]
    master["svg_viewBox"] = inspection["viewBox"]
    master["master_geometry_status"] = "SOURCE_INSPECTED_GEOMETRY_EXTRACTION_PENDING"
    master["source_text_candidates"] = inspection["area_like_text"]
    MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    return master


def main():
    print("--- BA0122 OFFICIAL 2D SOURCE AUDIT ---")
    payload = download_source()
    inspection = inspect_svg(payload)
    INSPECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSPECTION_PATH.write_text(json.dumps(inspection, ensure_ascii=False, indent=2), encoding="utf-8")
    master = update_master(inspection)

    print(f"Źródło: {SOURCE_URL}")
    print(f"Zapisano: {SOURCE_PATH}")
    print(f"SHA256: {inspection['sha256']}")
    print(f"SVG viewBox: {inspection['viewBox']}")
    print(f"Elementy SVG: {inspection['element_counts']}")
    print(f"Teksty z polami m²: {inspection['area_like_text']}")
    print(f"Master status: {master['master_geometry_status']}")
    print(f"Raport: {INSPECTION_PATH}")
    print()
    print("Następny krok: parsowanie konturów ścian i otworów z oficjalnego SVG.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"BA0122 AUDIT ERROR: {exc}", file=sys.stderr)
        raise
