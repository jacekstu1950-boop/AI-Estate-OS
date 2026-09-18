from adapters.skanska_stilla_snapshot import compare_snapshots


def make_snapshot(records):
    return {
        "developer": "Skanska",
        "project": "Stilla",
        "captured_at": "2026-09-18T15:00:00",
        "count": len(records),
        "records": records,
    }


def test_detects_added_and_removed():
    old = make_snapshot([
        {"apartment_code": "BA0005", "price_pln": 500000},
        {"apartment_code": "BA0122", "price_pln": 800000},
    ])
    new = make_snapshot([
        {"apartment_code": "BA0005", "price_pln": 500000},
        {"apartment_code": "BA0688", "price_pln": 900000},
    ])

    changes = compare_snapshots(old, new)
    by_code = {item["apartment_code"]: item for item in changes}

    assert by_code["BA0122"]["change"] == "REMOVED"
    assert by_code["BA0688"]["change"] == "ADDED"
    assert by_code["BA0005"]["change"] == "UNCHANGED"


def test_detects_price_change():
    old = make_snapshot([
        {
            "apartment_code": "BA0005",
            "price_pln": 500000,
            "availability": "available",
        }
    ])
    new = make_snapshot([
        {
            "apartment_code": "BA0005",
            "price_pln": 510000,
            "availability": "available",
        }
    ])

    changes = compare_snapshots(old, new)

    assert changes[0]["change"] == "CHANGED"
    assert changes[0]["fields"]["price_pln"] == {
        "old": 500000,
        "new": 510000,
    }


def test_detects_availability_change():
    old = make_snapshot([
        {
            "apartment_code": "BA0005",
            "availability": "available",
        }
    ])
    new = make_snapshot([
        {
            "apartment_code": "BA0005",
            "availability": "sold",
        }
    ])

    changes = compare_snapshots(old, new)

    assert changes[0]["change"] == "CHANGED"
    assert changes[0]["fields"]["availability"] == {
        "old": "available",
        "new": "sold",
    }
