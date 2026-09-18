import argparse
import json
from pathlib import Path

from adapters.skanska_stilla_snapshot import (
    build_snapshot,
    discover_apartment_codes,
    save_snapshot,
    verify_discovered_apartments,
)
from adapters.skanska_stilla_diff import (
    compare_latest_two,
    save_diff,
)

SNAPSHOT_DIR = Path("snapshots") / "skanska_stilla"


def summarize_verification(records):
    pass_count = sum(
        item.get("identity_status") == "PASS"
        and item.get("evidence_status") == "PASS"
        for item in records
    )
    fail_count = sum(
        item.get("identity_status") == "FAIL"
        for item in records
    )
    unknown_count = len(records) - pass_count - fail_count

    return {
        "PASS": pass_count,
        "FAIL": fail_count,
        "UNKNOWN": unknown_count,
    }


def run_pipeline(headless=True):
    discovered = discover_apartment_codes(headless=headless)
    verified = verify_discovered_apartments(
        discovered,
        headless=headless,
    )

    verification_summary = summarize_verification(verified)

    if verification_summary["FAIL"] > 0 or verification_summary["UNKNOWN"] > 0:
        return {
            "status": "BLOCKED",
            "discovered_count": len(discovered),
            "verification": verification_summary,
            "snapshot_path": None,
            "diff": None,
        }

    snapshot = build_snapshot(verified)
    snapshot_path, latest_path = save_snapshot(
        snapshot,
        directory=SNAPSHOT_DIR,
    )

    diff_result = compare_latest_two(SNAPSHOT_DIR)
    diff_path = save_diff(diff_result)

    return {
        "status": "OK",
        "discovered_count": len(discovered),
        "verification": verification_summary,
        "snapshot_path": str(snapshot_path),
        "latest_path": str(latest_path),
        "diff_path": str(diff_path),
        "diff": diff_result,
    }


def print_result(result):
    print("\n--- SKANSKA STILLA PIPELINE ---")
    print(f"Status: {result['status']}")
    print(f"Wykryto lokali: {result['discovered_count']}")

    verification = result["verification"]
    print(
        "Weryfikacja: "
        f"PASS={verification['PASS']}, "
        f"FAIL={verification['FAIL']}, "
        f"UNKNOWN={verification['UNKNOWN']}"
    )

    if result["status"] != "OK":
        print(
            "Snapshot nie został zapisany, ponieważ co najmniej jeden lokal "
            "nie przeszedł walidacji."
        )
        return

    print(f"Snapshot: {result['snapshot_path']}")
    print(f"Latest: {result['latest_path']}")

    diff_result = result["diff"]

    if diff_result["status"] == "NOT_ENOUGH_SNAPSHOTS":
        print(
            "Diff: brak wystarczającej liczby snapshotów "
            f"(liczba={diff_result['snapshot_count']})."
        )
    else:
        summary = diff_result["summary"]
        print(
            "Diff: "
            f"ADDED={summary['ADDED']}, "
            f"REMOVED={summary['REMOVED']}, "
            f"CHANGED={summary['CHANGED']}, "
            f"UNCHANGED={summary['UNCHANGED']}"
        )

    print(f"Raport diff: {result['diff_path']}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Jedno polecenie: discovery -> walidacja -> snapshot -> diff "
            "dla Skanska Stilla."
        )
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Uruchamia Playwright z widocznym oknem przeglądarki.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Dodatkowo wypisuje pełny wynik jako JSON.",
    )

    args = parser.parse_args()
    result = run_pipeline(headless=not args.show_browser)
    print_result(result)

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
