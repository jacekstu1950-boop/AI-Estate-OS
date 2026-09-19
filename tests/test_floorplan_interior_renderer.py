import pytest

from geometry.test_floorplan_interior_renderer import build_html
from geometry.test_floorplan_pipeline import build_3d_scene, parse_test_floorplan


def make_scene():
    model = parse_test_floorplan("fixtures/floorplans/test_apartment.svg")
    return build_3d_scene(model)


def test_scene_contains_35mm_interior_camera():
    scene = make_scene()
    camera = scene["camera_presets"]["interior_living"]

    assert camera["status"] == "TEST_PRESET"
    assert camera["lens_mm"] == 35
    assert camera["eye_height_m"] == 1.65
    assert camera["position_m"][2] == 1.65


def test_interior_renderer_builds_self_contained_html():
    html = build_html(make_scene())

    assert "pierwsza testowa wizualizacja wnętrza" in html
    assert "kamera 35 mm" in html
    assert "OWN_TEST_ASSET" in html
    assert "TEST_PRESET" in html
    assert "Przeciągnij myszą" in html
    assert "__PAYLOAD_JSON__" not in html


def test_interior_renderer_rejects_non_owned_scene():
    scene = make_scene()
    scene["source_rights_status"] = "UNKNOWN"

    with pytest.raises(ValueError, match="OWN_TEST_ASSET"):
        build_html(scene)


def test_interior_renderer_rejects_missing_camera():
    scene = make_scene()
    scene["camera_presets"] = {}

    with pytest.raises(ValueError, match="interior_living"):
        build_html(scene)
