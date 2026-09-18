import json
from pathlib import Path

SOURCE = Path("snapshots/skanska_stilla/stilla_2026-09-18T16-19-40.json")
TARGET = Path("snapshots/skanska_stilla/stilla_2026-09-18T16-30-00.json")


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = data["records"]

    by_code = {item["apartment_code"]: item for item in records}

    # 1. Zmiana ceny i dostępności BA0005
    if "BA0005" in by_code:
        by_code["BA0005"]["price_pln"] = 555000.00
        by_code["BA0005"]["availability"] = "sold"

    # 2. Usunięcie BA0688
    records = [
        item for item in records
        if item.get("apartment_code") != "BA0688"
    ]

    # 3. Dodanie rekordu testowego
    records.append({
        "developer": "Skanska",
        "project": "Stilla",
        "apartment_code": "ZZ9999",
        "building": "Z",
        "rooms": 2,
        "floor": 1,
        "area_m2": 50.0,
        "price_pln": 700000.0,
        "price_per_m2_pln": 14000.0,
        "availability": "available",
        "source_url": "TEST_ONLY",
        "retrieved_at": "2026-09-18T16:30:00",
        "identity_status": "PASS",
        "evidence_status": "PASS",
        "floorplan_rights_status": "UNKNOWN",
        "conflicts": [],
        "notes": ["TEST INTEGRACYJNY"],
    })

    data["captured_at"] = "2026-09-18T16:30:00"
    data["count"] = len(records)
    data["records"] = records

    TARGET.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Utworzono: {TARGET}")


if __name__ == "__main__":
    main()
