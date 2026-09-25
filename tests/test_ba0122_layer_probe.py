from geometry.ba0122_layer_probe import classify


def test_classify_basic_layers():
    records = [
        {
            "index": 0,
            "class": "B",
            "clip_path": "url(#Bz)",
            "stroke": "#000",
            "fill": "none",
            "bbox_area": 12000,
            "commands": {"L": 4},
        },
        {
            "index": 1,
            "class": "F",
            "clip_path": "url(#Bx)",
            "stroke": None,
            "fill": "#fff",
            "bbox_area": 20,
            "commands": {"C": 8},
        },
    ]
    layers = classify(records)
    assert layers["class_B"] == [0]
    assert layers["class_F"] == [1]
    assert layers["stroked"] == [0]
    assert layers["very_large"] == [0]
    assert layers["line_rich"] == [0]
    assert layers["curve_dense"] == [1]
