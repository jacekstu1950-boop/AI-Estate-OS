import json
from pathlib import Path

from geometry.ba0122_source_audit import extract_area_like_text, sha256_bytes


def test_extract_area_like_text():
    values = ["47.49 m²", "8,50 m2", "BA0122", "2 pokoje"]
    assert extract_area_like_text(values) == ["47.49 m²", "8,50 m2"]


def test_sha256_is_deterministic():
    assert sha256_bytes(b"BA0122") == sha256_bytes(b"BA0122")


def test_master_manifest_has_verified_official_facts():
    master = json.loads(Path("geometry/master/BA0122.master.json").read_text(encoding="utf-8"))
    assert master["apartment_code"] == "BA0122"
    assert master["official_area_m2"] == 47.49
    assert master["official_balcony_area_m2"] == 8.50
    assert master["rights_status"] == "USER_CONFIRMED_PERMISSION"
