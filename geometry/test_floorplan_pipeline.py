import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path

SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


@dataclass(frozen=True)
class Room:
    room_id: str
    name: str
    room_type: str
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float

    @property
    def area_m2(self):
        return round((self.width_cm * self.height_cm) / 10000, 2)


def _num(value):
    return float(value)


def parse_test_floorplan(path):
    root = ET.parse(path).getroot()
    apartment = root.find(".//svg:g[@id='apartment']", SVG_NS)
    if apartment is None:
        raise ValueError("Brak grupy apartment w rzucie testowym.")

    unit = apartment.attrib.get("data-unit")
    if unit != "cm":
        raise ValueError(f"Nieobsługiwana jednostka: {unit!r}")

    height_cm = _num(apartment.attrib["data-height-cm"])
    rooms = []

    for rect in apartment.findall("svg:rect", SVG_NS):
        room_id = rect.attrib.get("id", "")
        if not room_id.startswith("room-"):
            continue
        rooms.append(
            Room(
                room_id=room_id,
                name=rect.attrib["data-room-name"],
                room_type=rect.attrib["data-room-type"],
                x_cm=_num(rect.attrib["x"]),
                y_cm=_num(rect.attrib["y"]),
                width_cm=_num(rect.attrib["width"]),
                height_cm=_num(rect.attrib["height"]),
            )
        )

    openings = []
    for line in apartment.findall("svg:line", SVG_NS):
        opening_type = line.attrib.get("data-opening-type")
        if not opening_type:
            continue
        openings.append(
            {
                "id": line.attrib["id"],
                "type": opening_type,
                "x1_cm": _num(line.attrib["x1"]),
                "y1_cm": _num(line.attrib["y1"]),
                "x2_cm": _num(line.attrib["x2"]),
                "y2_cm": _num(line.attrib["y2"]),
                "width_cm": _num(line.attrib["data-width-cm"]),
                "height_cm": _num(line.attrib["data-height-cm"]),
                "sill_cm": (
                    _num(line.attrib["data-sill-cm"])
                    if "data-sill-cm" in line.attrib
                    else None
                ),
            }
        )

    if not rooms:
        raise ValueError("Rzut testowy nie zawiera żadnych pomieszczeń.")

    return {
        "source_type": "synthetic_test_floorplan",
        "rights_status": "OWN_TEST_ASSET",
        "unit": "cm",
        "wall_height_cm": height_cm,
        "rooms": [
            {
                **asdict(room),
                "area_m2": room.area_m2,
            }
            for room in rooms
        ],
        "openings": openings,
    }


def validate_geometry(model):
    issues = []

    if model["rights_status"] != "OWN_TEST_ASSET":
        issues.append("Źródło nie jest oznaczone jako własny zasób testowy.")

    if model["wall_height_cm"] <= 0:
        issues.append("Wysokość ścian musi być dodatnia.")

    room_ids = [room["room_id"] for room in model["rooms"]]
    if len(room_ids) != len(set(room_ids)):
        issues.append("Identyfikatory pomieszczeń nie są unikalne.")

    for room in model["rooms"]:
        if room["width_cm"] <= 0 or room["height_cm"] <= 0:
            issues.append(f"Niepoprawne wymiary pomieszczenia {room['room_id']}.")

    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }


def build_3d_scene(model):
    validation = validate_geometry(model)
    if validation["status"] != "PASS":
        raise ValueError("Model 2D nie przeszedł walidacji.")

    objects = []
    height_m = model["wall_height_cm"] / 100

    for room in model["rooms"]:
        objects.append(
            {
                "id": room["room_id"],
                "type": "room_volume",
                "name": room["name"],
                "origin_m": [
                    room["x_cm"] / 100,
                    room["y_cm"] / 100,
                    0.0,
                ],
                "size_m": [
                    room["width_cm"] / 100,
                    room["height_cm"] / 100,
                    height_m,
                ],
                "area_m2": room["area_m2"],
            }
        )

    return {
        "scene_type": "deterministic_test_3d_scene",
        "source_rights_status": model["rights_status"],
        "geometry_validation": validation,
        "objects": objects,
        "openings": model["openings"],
    }


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    source = Path("fixtures/floorplans/test_apartment.svg")
    geometry_path = Path("build/test_floorplan_geometry.json")
    scene_path = Path("build/test_floorplan_scene3d.json")

    geometry = parse_test_floorplan(source)
    scene = build_3d_scene(geometry)

    save_json(geometry, geometry_path)
    save_json(scene, scene_path)

    print("--- TEST FLOORPLAN 2D -> GEOMETRY -> 3D ---")
    print(f"Źródło: {source}")
    print(f"Prawa: {geometry['rights_status']}")
    print(f"Walidacja: {scene['geometry_validation']['status']}")
    print(f"Pomieszczenia: {len(geometry['rooms'])}")
    print(f"Geometria: {geometry_path}")
    print(f"Scena 3D: {scene_path}")


if __name__ == "__main__":
    main()
