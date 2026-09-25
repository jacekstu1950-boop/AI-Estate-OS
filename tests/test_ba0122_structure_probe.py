from geometry.ba0122_structure_probe import classify

def test_defs_and_direct_paths_are_separated():
    records = [
        {
            "index":0, "in_defs":True, "in_clipPath":False,
            "referenced_by_use":True, "bbox_area":100,
            "commands":{"C":8}
        },
        {
            "index":1, "in_defs":False, "in_clipPath":False,
            "referenced_by_use":False, "bbox_area":12000,
            "commands":{"L":5}
        },
    ]
    layers = classify(records)
    assert layers["defs_paths"] == [0]
    assert layers["referenced_by_use"] == [0]
    assert layers["direct_render_paths"] == [1]
    assert layers["direct_unreferenced"] == [1]
    assert layers["direct_very_large"] == [1]
    assert layers["direct_line_rich"] == [1]
