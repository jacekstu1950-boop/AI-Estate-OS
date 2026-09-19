import pytest

from geometry.test_floorplan_material_renderer import build_html
from geometry.test_floorplan_pipeline import build_3d_scene, parse_test_floorplan


def make_scene():
    model = parse_test_floorplan("fixtures/floorplans/test_apartment.svg")
    return build_3d_scene(model)


def test_scene_contains_test_materials_and_lighting():
    scene = make_scene()
    preset = scene["visualization_preset"]

    assert preset["status"] == "TEST_STAGING"
    assert "warm_white_plaster_test" in preset["materials"]
    assert "oak_light_test" in preset["materials"]
    assert preset["lighting"]["ambient_intensity"] > 0
    assert preset["lighting"]["window_light_intensity"] > 0
    assert len(preset["staging_objects"]) == 2


def test_geometry_objects_keep_material_ids():
    scene = make_scene()
    floors = [x for x in scene["objects"] if x["type"] == "room_floor"]
    walls = [x for x in scene["objects"] if x["type"] == "wall_segment"]

    assert all(x["material_id"] == "oak_light_test" for x in floors)
    assert all(x["material_id"] == "warm_white_plaster_test" for x in walls)


def test_material_renderer_builds_self_contained_html():
    html = build_html(make_scene())

    assert "Etap 5E: materiały i światło" in html
    assert "TEST_STAGING" in html
    assert "Meble testowe" in html
    assert "drawWindowGlow" in html
    assert "drawSoftShadow" in html
    assert "__PAYLOAD_JSON__" not in html


def test_material_renderer_rejects_non_owned_scene():
    scene = make_scene()
    scene["source_rights_status"] = "UNKNOWN"

    with pytest.raises(ValueError, match="OWN_TEST_ASSET"):
        build_html(scene)


def test_material_renderer_rejects_missing_visual_preset():
    scene = make_scene()
    scene.pop("visualization_preset")

    with pytest.raises(ValueError, match="TEST_STAGING"):
        build_html(scene)
