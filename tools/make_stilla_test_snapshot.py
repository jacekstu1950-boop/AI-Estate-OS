import argparse
import json
from pathlib import Path

DEFAULT_SOURCE_DIR = Path("snapshots") / "skanska_stilla"
DEFAULT_TARGET = Path("tests") / "fixtures" / "skanska_stilla" / "stilla_test_modified.json"


def find_latest_live_snapshot(directory=DEFAULT_SOURCE_DIR):
    files = sorted(
        path
        for path in Path(directory).glob("stilla_*.json")
        if path.is_file()
    )
    if not files:
        raise FileNotFoundError(
            "Brak live snapshotów w snapshots/skanska_stilla."
        )
    return files[-1]


def build_modified_test_snapshot(source_path):
    data = json.loads(Path(source_path).read_text(encoding="utf-8"))
    records = data["records"]

    by_code = {
        item["apartment_code"]: item
        for item in records
        if item.get("apartment_code")
    }

    if "BA0005" in by_code:
        by_code["BA0005"]["price_pln"] = 555000.00
        by_code["BA0005"]["availability"] = "sold"

    records = [
        item for item in records
        if item.get("apartment_code") != "BA0688"
    ]

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
        "retrieved_at": "TEST_ONLY",
        "identity_status": "PASS",
        "evidence_status": "PASS",
        "floorplan_rights_status": "UNKNOWN",
        "conflicts": [],
        "notes": ["TEST INTEGRACYJNY"],
    })

    data["captured_at"] = "TEST_ONLY"
    data["count"] = len(records)
    data["records"] = records
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Tworzy syntetyczny snapshot testowy poza katalogiem live."
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Opcjonalna ścieżka do bazowego live snapshotu.",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help="Ścieżka wyjściowa dla danych testowych.",
    )
    args = parser.parse_args()

    source = Path(args.source) if args.source else find_latest_live_snapshot()
    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)

    data = build_modified_test_snapshot(source)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Źródło live: {source}")
    print(f"Utworzono test fixture: {target}")


if __name__ == "__main__":
    main()
