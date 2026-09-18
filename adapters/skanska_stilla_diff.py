import json
from pathlib import Path

from adapters.skanska_stilla_snapshot import compare_snapshots

SNAPSHOT_DIR = Path("snapshots") / "skanska_stilla"
DIFF_FILE = SNAPSHOT_DIR / "changes_latest.json"


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def find_snapshot_files(directory=SNAPSHOT_DIR):
    directory = Path(directory)
    if not directory.exists():
        return []

    return sorted(
        path
        for path in directory.glob("stilla_*.json")
        if path.is_file()
    )


def compare_latest_two(directory=SNAPSHOT_DIR):
    files = find_snapshot_files(directory)

    if len(files) < 2:
        return {
            "status": "NOT_ENOUGH_SNAPSHOTS",
            "snapshot_count": len(files),
            "changes": [],
        }

    old_path = files[-2]
    new_path = files[-1]

    old_snapshot = load_json(old_path)
    new_snapshot = load_json(new_path)
    changes = compare_snapshots(old_snapshot, new_snapshot)

    summary = {
        "ADDED": 0,
        "REMOVED": 0,
        "CHANGED": 0,
        "UNCHANGED": 0,
    }

    for item in changes:
        summary[item["change"]] += 1

    return {
        "status": "OK",
        "old_snapshot": str(old_path),
        "new_snapshot": str(new_path),
        "summary": summary,
        "changes": changes,
    }


def save_diff(result, path=DIFF_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    return path


def main():
    result = compare_latest_two()
    path = save_diff(result)

    print("\n--- SKANSKA STILLA DIFF ---")

    if result["status"] != "OK":
        print(
            "Brak wystarczającej liczby snapshotów. "
            f"Znaleziono: {result['snapshot_count']}. "
            "Uruchom snapshot ponownie później, aby mieć co najmniej 2."
        )
        print(f"Zapisano: {path}")
        return

    summary = result["summary"]

    print(f"Poprzedni snapshot: {result['old_snapshot']}")
    print(f"Najnowszy snapshot: {result['new_snapshot']}")
    print(
        "Zmiany: "
        f"ADDED={summary['ADDED']}, "
        f"REMOVED={summary['REMOVED']}, "
        f"CHANGED={summary['CHANGED']}, "
        f"UNCHANGED={summary['UNCHANGED']}"
    )
    print(f"Zapisano: {path}")


if __name__ == "__main__":
    main()
