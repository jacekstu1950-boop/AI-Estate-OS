from geometry.ba0122_semantic_class_probe import collect
import xml.etree.ElementTree as ET

def test_collect_semantic_css_layers():
    root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"><path class="C D E H I K" d="M0 0L10 0"/><path class="B G J" d="M0 0L1 1"/></svg>')
    layers=collect(root)
    assert layers["black_024_no_fill"] == [0]
    assert layers["unclipped_black_024_no_fill"] == [0]
    assert layers["gray_012"] == [1]
    assert layers["clipped_B_gray"] == [1]
