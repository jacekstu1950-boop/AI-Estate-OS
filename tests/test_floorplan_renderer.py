from geometry.test_floorplan_pipeline import build_3d_scene, parse_test_floorplan
from geometry.test_floorplan_renderer import build_html


def test_renderer_accepts_owned_valid_scene():
    model = parse_test_floorplan("fixtures/floorplans/test_apartment.svg")
    scene = build_3d_scene(model)

    html = build_html(scene)

    assert "testowy renderer 3D" in html
    assert "OWN_TEST_ASSET" in html
    assert "geometry_validation" in html
    assert "floor-room-living" in html
    assert "wall_segment" in html
    assert "ściany, drzwi i okna" in html
    assert "Przeciągnij myszą" in html


def test_renderer_rejects_non_owned_asset():
    model = parse_test_floorplan("fixtures/floorplans/test_apartment.svg")
    scene = build_3d_scene(model)
    scene["source_rights_status"] = "UNKNOWN"

    try:
        build_html(scene)
    except ValueError as exc:
        assert "OWN_TEST_ASSET" in str(exc)
    else:
        raise AssertionError("Renderer powinien odrzucić źródło bez OWN_TEST_ASSET")


def test_renderer_rejects_failed_geometry():
    model = parse_test_floorplan("fixtures/floorplans/test_apartment.svg")
    scene = build_3d_scene(model)
    scene["geometry_validation"] = {"status": "FAIL", "issues": ["test"]}

    try:
        build_html(scene)
    except ValueError as exc:
        assert "walidacji geometrii" in str(exc)
    else:
        raise AssertionError("Renderer powinien odrzucić scenę z FAIL")
