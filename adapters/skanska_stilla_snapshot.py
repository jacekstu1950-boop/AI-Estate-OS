import json
from datetime import datetime
from pathlib import Path

from adapters.skanska_stilla_listing import (
    discover_apartment_codes,
    verify_discovered_apartments,
)

SNAPSHOT_DIR = Path("snapshots") / "skanska_stilla"


def build_snapshot(records, captured_at=None):
    if captured_at is None:
        captured_at = datetime.now().isoformat(timespec="seconds")

    return {
        "developer": "Skanska",
        "project": "Stilla",
        "captured_at": captured_at,
        "count": len(records),
        "records": records,
    }


def save_snapshot(snapshot, directory=SNAPSHOT_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    safe_timestamp = snapshot["captured_at"].replace(":", "-")
    path = directory / f"stilla_{safe_timestamp}.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)

    latest_path = directory / "latest.json"
    with latest_path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)

    return path, latest_path


def record_index(snapshot):
    return {
        item["apartment_code"]: item
        for item in snapshot["records"]
        if item.get("apartment_code")
    }


def compare_snapshots(old_snapshot, new_snapshot):
    old = record_index(old_snapshot)
    new = record_index(new_snapshot)

    changes = []

    for code in sorted(set(old) | set(new)):
        old_item = old.get(code)
        new_item = new.get(code)

        if old_item is None:
            changes.append({
                "apartment_code": code,
                "change": "ADDED",
                "old": None,
                "new": new_item,
            })
            continue

        if new_item is None:
            changes.append({
                "apartment_code": code,
                "change": "REMOVED",
                "old": old_item,
                "new": None,
            })
            continue

        tracked_fields = [
            "price_pln",
            "price_per_m2_pln",
            "availability",
            "area_m2",
            "rooms",
            "floor",
            "building",
            "identity_status",
            "evidence_status",
        ]

        field_changes = {}

        for field in tracked_fields:
            if old_item.get(field) != new_item.get(field):
                field_changes[field] = {
                    "old": old_item.get(field),
                    "new": new_item.get(field),
                }

        if field_changes:
            changes.append({
                "apartment_code": code,
                "change": "CHANGED",
                "fields": field_changes,
            })
        else:
            changes.append({
                "apartment_code": code,
                "change": "UNCHANGED",
            })

    return changes


def run_snapshot(headless=True):
    discovered = discover_apartment_codes(headless=headless)
    verified = verify_discovered_apartments(discovered, headless=headless)
    snapshot = build_snapshot(verified)
    return save_snapshot(snapshot)


if __name__ == "__main__":
    snapshot_path, latest_path = run_snapshot(headless=True)
    print(f"Zapisano snapshot: {snapshot_path}")
    print(f"Zaktualizowano latest: {latest_path}")
