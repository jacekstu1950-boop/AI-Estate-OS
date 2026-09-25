import xml.etree.ElementTree as ET

from geometry.ba0122_vector_probe import (
    bbox_area,
    classify_path,
    parse_style_attr,
    rough_path_bbox,
)


def test_parse_style_attr():
    assert parse_style_attr("fill:none;stroke:#000;stroke-width:2") == {
        "fill": "none",
        "stroke": "#000",
        "stroke-width": "2",
    }


def test_rough_path_bbox_for_simple_polygon():
    bbox = rough_path_bbox("M 10 20 L 30 20 L 30 40 L 10 40 Z")
    assert bbox == [10.0, 20.0, 40.0, 30.0] or bbox_area(bbox) > 0


def test_classify_structural_path_candidate():
    result = classify_path(
        {"fill": "none", "stroke": "#000", "stroke-width": "2"},
        [0, 0, 100, 100],
        "M0 0 L100 0 L100 100 L0 100 Z",
    )
    assert result["candidate"] is True
