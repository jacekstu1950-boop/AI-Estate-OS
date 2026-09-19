import json
import math
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


def _line_orientation(line):
    x1, y1 = line["x1_cm"], line["y1_cm"]
    x2, y2 = line["x2_cm"], line["y2_cm"]
    if math.isclose(y1, y2):
        return "horizontal"
    if math.isclose(x1, x2):
        return "vertical"
    raise ValueError(f"Ściana {line['id']} nie jest ortogonalna.")


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

    walls = []
    for line in apartment.findall(".//svg:line[@data-wall='true']", SVG_NS):
        wall = {
            "id": line.attrib["id"],
            "x1_cm": _num(line.attrib["x1"]),
            "y1_cm": _num(line.attrib["y1"]),
            "x2_cm": _num(line.attrib["x2"]),
            "y2_cm": _num(line.attrib["y2"]),
            "thickness_cm": _num(line.attrib["data-wall-thickness-cm"]),
        }
        wall["orientation"] = _line_orientation(wall)
        walls.append(wall)

    openings = []
    for line in apartment.findall(".//svg:line[@data-opening-type]", SVG_NS):
        openings.append(
            {
                "id": line.attrib["id"],
                "type": line.attrib["data-opening-type"],
                "wall_id": line.attrib["data-wall-id"],
                "x1_cm": _num(line.attrib["x1"]),
                "y1_cm": _num(line.attrib["y1"]),
                "x2_cm": _num(line.attrib["x2"]),
                "y2_cm": _num(line.attrib["y2"]),
                "width_cm": _num(line.attrib["data-width-cm"]),
                "height_cm": _num(line.attrib["data-height-cm"]),
                "sill_cm": (
                    _num(line.attrib["data-sill-cm"])
                    if "data-sill-cm" in line.attrib
                    else 0.0
                ),
            }
        )

    if not rooms:
        raise ValueError("Rzut testowy nie zawiera żadnych pomieszczeń.")
    if not walls:
        raise ValueError("Rzut testowy nie zawiera żadnych ścian.")

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
        "walls": walls,
        "openings": openings,
    }


def validate_geometry(model):
    issues = []

    if model["rights_status"] != "OWN_TEST_ASSET":
        issues.append("Źródło nie jest oznaczone jako własny zasób testowy.")

    wall_height = model["wall_height_cm"]
    if wall_height <= 0:
        issues.append("Wysokość ścian musi być dodatnia.")

    room_ids = [room["room_id"] for room in model["rooms"]]
    if len(room_ids) != len(set(room_ids)):
        issues.append("Identyfikatory pomieszczeń nie są unikalne.")

    for room in model["rooms"]:
        if room["width_cm"] <= 0 or room["height_cm"] <= 0:
            issues.append(f"Niepoprawne wymiary pomieszczenia {room['room_id']}.")

    wall_ids = {wall["id"] for wall in model["walls"]}
    for wall in model["walls"]:
        if wall["thickness_cm"] <= 0:
            issues.append(f"Niepoprawna grubość ściany {wall['id']}.")

    for opening in model["openings"]:
        if opening["wall_id"] not in wall_ids:
            issues.append(
                f"Otwór {opening['id']} wskazuje nieistniejącą ścianę {opening['wall_id']}."
            )
            continue
        if opening["width_cm"] <= 0 or opening["height_cm"] <= 0:
            issues.append(f"Niepoprawne wymiary otworu {opening['id']}.")
        if opening["sill_cm"] < 0:
            issues.append(f"Niepoprawna wysokość parapetu {opening['id']}.")
        if opening["sill_cm"] + opening["height_cm"] > wall_height:
            issues.append(
                f"Otwór {opening['id']} przekracza wysokość ściany."
            )

    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }


def _wall_axis_interval(wall):
    if wall["orientation"] == "horizontal":
        return sorted([wall["x1_cm"], wall["x2_cm"]])
    return sorted([wall["y1_cm"], wall["y2_cm"]])


def _opening_axis_interval(opening, wall):
    if wall["orientation"] == "horizontal":
        return sorted([opening["x1_cm"], opening["x2_cm"]])
    return sorted([opening["y1_cm"], opening["y2_cm"]])


def _wall_box(wall, start_cm, end_cm, z0_cm, z1_cm, suffix):
    thickness = wall["thickness_cm"]
    length = end_cm - start_cm
    if length <= 0 or z1_cm <= z0_cm:
        return None

    if wall["orientation"] == "horizontal":
        x_cm = start_cm
        y_cm = wall["y1_cm"] - thickness / 2
        width_cm = length
        depth_cm = thickness
    else:
        x_cm = wall["x1_cm"] - thickness / 2
        y_cm = start_cm
        width_cm = thickness
        depth_cm = length

    return {
        "id": f"{wall['id']}-{suffix}",
        "type": "wall_segment",
        "name": wall["id"],
        "origin_m": [x_cm / 100, y_cm / 100, z0_cm / 100],
        "size_m": [width_cm / 100, depth_cm / 100, (z1_cm - z0_cm) / 100],
        "source_wall_id": wall["id"],
    }


def build_wall_segments(model):
    wall_height = model["wall_height_cm"]
    segments = []

    openings_by_wall = {}
    for opening in model["openings"]:
        openings_by_wall.setdefault(opening["wall_id"], []).append(opening)

    for wall in model["walls"]:
        wall_start, wall_end = _wall_axis_interval(wall)
        openings = sorted(
            openings_by_wall.get(wall["id"], []),
            key=lambda opening: _opening_axis_interval(opening, wall)[0],
        )

        cursor = wall_start
        part = 0

        for opening in openings:
            opening_start, opening_end = _opening_axis_interval(opening, wall)

            if opening_start < wall_start or opening_end > wall_end:
                raise ValueError(
                    f"Otwór {opening['id']} wychodzi poza ścianę {wall['id']}."
                )

            before = _wall_box(
                wall, cursor, opening_start, 0, wall_height, f"full-{part}"
            )
            if before:
                segments.append(before)

            sill = opening["sill_cm"]
            top = sill + opening["height_cm"]

            below = _wall_box(
                wall, opening_start, opening_end, 0, sill, f"below-{opening['id']}"
            )
            if below:
                segments.append(below)

            above = _wall_box(
                wall,
                opening_start,
                opening_end,
                top,
                wall_height,
                f"above-{opening['id']}",
            )
            if above:
                segments.append(above)

            cursor = opening_end
            part += 1

        after = _wall_box(
            wall, cursor, wall_end, 0, wall_height, f"full-{part}"
        )
        if after:
            segments.append(after)

    return segments


def build_3d_scene(model):
    validation = validate_geometry(model)
    if validation["status"] != "PASS":
        raise ValueError("Model 2D nie przeszedł walidacji.")

    objects = []

    for room in model["rooms"]:
        objects.append(
            {
                "id": f"floor-{room['room_id']}",
                "type": "room_floor",
                "name": room["name"],
                "origin_m": [
                    room["x_cm"] / 100,
                    room["y_cm"] / 100,
                    -0.05,
                ],
                "size_m": [
                    room["width_cm"] / 100,
                    room["height_cm"] / 100,
                    0.05,
                ],
                "area_m2": room["area_m2"],
            }
        )

    objects.extend(build_wall_segments(model))

    return {
        "scene_type": "architectural_test_3d_scene",
        "source_rights_status": model["rights_status"],
        "geometry_validation": validation,
        "wall_height_m": model["wall_height_cm"] / 100,
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

    wall_segments = [
        obj for obj in scene["objects"] if obj["type"] == "wall_segment"
    ]

    print("--- TEST FLOORPLAN 2D -> ARCHITECTURAL GEOMETRY -> 3D ---")
    print(f"Źródło: {source}")
    print(f"Prawa: {geometry['rights_status']}")
    print(f"Walidacja: {scene['geometry_validation']['status']}")
    print(f"Pomieszczenia: {len(geometry['rooms'])}")
    print(f"Ściany źródłowe: {len(geometry['walls'])}")
    print(f"Segmenty ścian po wycięciu otworów: {len(wall_segments)}")
    print(f"Otwory: {len(geometry['openings'])}")
    print(f"Geometria: {geometry_path}")
    print(f"Scena 3D: {scene_path}")


if __name__ == "__main__":
    main()
