from pathlib import Path

from geometry.test_floorplan_pipeline import (
    build_3d_scene,
    build_wall_segments,
    parse_test_floorplan,
    validate_geometry,
)


FIXTURE = Path("fixtures/floorplans/test_apartment.svg")


def test_owned_test_floorplan_parses_to_architectural_geometry():
    model = parse_test_floorplan(FIXTURE)

    assert model["source_type"] == "synthetic_test_floorplan"
    assert model["rights_status"] == "OWN_TEST_ASSET"
    assert model["wall_height_cm"] == 270
    assert len(model["rooms"]) == 4
    assert len(model["walls"]) == 7
    assert len(model["openings"]) == 2


def test_test_floorplan_geometry_passes_validation():
    model = parse_test_floorplan(FIXTURE)
    validation = validate_geometry(model)

    assert validation == {"status": "PASS", "issues": []}


def test_room_areas_are_deterministic():
    model = parse_test_floorplan(FIXTURE)
    areas = {room["room_id"]: room["area_m2"] for room in model["rooms"]}

    assert areas["room-living"] == 12.54
    assert areas["room-bedroom"] == 6.93
    assert areas["room-bathroom"] == 3.55
    assert areas["room-hall"] == 7.34


def test_wall_segments_cut_door_and_window_openings():
    model = parse_test_floorplan(FIXTURE)
    segments = build_wall_segments(model)

    door_segments = [
        item
        for item in segments
        if item["source_wall_id"] == "wall-outer-bottom"
    ]
    window_segments = [
        item
        for item in segments
        if item["source_wall_id"] == "wall-outer-top"
    ]

    assert len(door_segments) == 3
    assert len(window_segments) == 4

    door_lintel = next(
        item for item in door_segments if "above-door-entry" in item["id"]
    )
    assert door_lintel["origin_m"][2] == 2.1
    assert door_lintel["size_m"][2] == 0.6

    window_lower = next(
        item for item in window_segments if "below-window-living" in item["id"]
    )
    window_upper = next(
        item for item in window_segments if "above-window-living" in item["id"]
    )
    assert window_lower["size_m"][2] == 0.9
    assert window_upper["origin_m"][2] == 2.1
    assert window_upper["size_m"][2] == 0.6


def test_3d_scene_contains_floors_and_architectural_walls():
    model = parse_test_floorplan(FIXTURE)
    scene = build_3d_scene(model)

    assert scene["geometry_validation"]["status"] == "PASS"
    assert scene["source_rights_status"] == "OWN_TEST_ASSET"
    assert scene["scene_type"] == "architectural_test_3d_scene"
    assert scene["wall_height_m"] == 2.7

    floors = [obj for obj in scene["objects"] if obj["type"] == "room_floor"]
    walls = [obj for obj in scene["objects"] if obj["type"] == "wall_segment"]

    assert len(floors) == 4
    assert len(walls) == 11

    living = next(obj for obj in floors if obj["id"] == "floor-room-living")
    assert living["origin_m"] == [0.6, 0.6, -0.05]
    assert living["size_m"] == [4.25, 2.95, 0.05]
