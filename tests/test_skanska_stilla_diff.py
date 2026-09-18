import json
from pathlib import Path

from adapters.skanska_stilla_diff import compare_latest_two


def write_snapshot(path, records):
    payload = {
        "developer": "Skanska",
        "project": "Stilla",
        "captured_at": "2026-09-18T16:00:00",
        "count": len(records),
        "records": records,
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_reports_not_enough_snapshots(tmp_path):
    write_snapshot(
        tmp_path / "stilla_2026-09-18T16-00-00.json",
        [{"apartment_code": "BA0005"}],
    )

    result = compare_latest_two(tmp_path)

    assert result["status"] == "NOT_ENOUGH_SNAPSHOTS"
    assert result["snapshot_count"] == 1
    assert result["changes"] == []


def test_compares_latest_two_snapshots(tmp_path):
    write_snapshot(
        tmp_path / "stilla_2026-09-18T16-00-00.json",
        [
            {
                "apartment_code": "BA0005",
                "price_pln": 500000,
                "availability": "available",
            },
            {
                "apartment_code": "BA0122",
                "price_pln": 800000,
                "availability": "available",
            },
        ],
    )

    write_snapshot(
        tmp_path / "stilla_2026-09-18T17-00-00.json",
        [
            {
                "apartment_code": "BA0005",
                "price_pln": 510000,
                "availability": "available",
            },
            {
                "apartment_code": "BA0688",
                "price_pln": 900000,
                "availability": "available",
            },
        ],
    )

    result = compare_latest_two(tmp_path)

    assert result["status"] == "OK"
    assert result["summary"] == {
        "ADDED": 1,
        "REMOVED": 1,
        "CHANGED": 1,
        "UNCHANGED": 0,
    }

    by_code = {
        item["apartment_code"]: item
        for item in result["changes"]
    }

    assert by_code["BA0005"]["change"] == "CHANGED"
    assert by_code["BA0122"]["change"] == "REMOVED"
    assert by_code["BA0688"]["change"] == "ADDED"
