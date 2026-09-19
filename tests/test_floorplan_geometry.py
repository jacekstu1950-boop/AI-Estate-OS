from pathlib import Path

from geometry.test_floorplan_pipeline import (
    build_3d_scene,
    parse_test_floorplan,
    validate_geometry,
)


FIXTURE = Path("fixtures/floorplans/test_apartment.svg")


def test_owned_test_floorplan_parses_to_geometry():
    model = parse_test_floorplan(FIXTURE)

    assert model["source_type"] == "synthetic_test_floorplan"
    assert model["rights_status"] == "OWN_TEST_ASSET"
    assert model["wall_height_cm"] == 270
    assert len(model["rooms"]) == 4
    assert len(model["openings"]) == 2


def test_test_floorplan_geometry_passes_validation():
    model = parse_test_floorplan(FIXTURE)
    validation = validate_geometry(model)

    assert validation == {"status": "PASS", "issues": []}


def test_room_areas_are_deterministic():
    model = parse_test_floorplan(FIXTURE)
    areas = {room["room_id"]: room["area_m2"] for room in model["rooms"]}

    assert areas["room-living"] == 12.9
    assert areas["room-bedroom"] == 7.2
    assert areas["room-bathroom"] == 3.74
    assert areas["room-hall"] == 7.65


def test_3d_scene_preserves_2d_geometry_and_height():
    model = parse_test_floorplan(FIXTURE)
    scene = build_3d_scene(model)

    assert scene["geometry_validation"]["status"] == "PASS"
    assert scene["source_rights_status"] == "OWN_TEST_ASSET"
    living = next(obj for obj in scene["objects"] if obj["id"] == "room-living")
    assert living["origin_m"] == [0.6, 0.6, 0.0]
    assert living["size_m"] == [4.3, 3.0, 2.7]
