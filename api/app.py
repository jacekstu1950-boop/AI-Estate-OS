import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

APP_VERSION = "0.6.0"
SNAPSHOT_DIR = Path("snapshots") / "skanska_stilla"
LATEST_FILE = SNAPSHOT_DIR / "latest.json"
CHANGES_FILE = SNAPSHOT_DIR / "changes_latest.json"
WEB_INDEX = Path("web") / "index.html"
WEB_APARTMENT = Path("web") / "apartment.html"
RIGHTS_FILE = Path("compliance") / "skanska_stilla_floorplan_rights.json"

app = FastAPI(
    title="AI-Estate-OS API",
    version=APP_VERSION,
    description="Minimal API exposing verified Skanska Stilla runtime data.",
)


def load_json_file(path: Path):
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Brak danych runtime: {path}",
        )

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Niepoprawny JSON w pliku {path}: {exc}",
        ) from exc


def no_cache_file(path: Path):
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Brak pliku {path}")
    return FileResponse(
        path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/", include_in_schema=False)
def frontend():
    return no_cache_file(WEB_INDEX)


@app.get("/mieszkanie/{apartment_code}", include_in_schema=False)
def apartment_frontend(apartment_code: str):
    return no_cache_file(WEB_APARTMENT)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-estate-os-api",
        "version": APP_VERSION,
    }


def load_floorplan_rights():
    return load_json_file(RIGHTS_FILE)


@app.get("/api/skanska/stilla/floorplan-rights")
def skanska_stilla_floorplan_rights():
    rights = load_floorplan_rights()
    return {
        "status": rights.get("status"),
        "developer": rights.get("developer"),
        "project": rights.get("project"),
        "checked_at": rights.get("checked_at"),
        "source_url": rights.get("source_url"),
        "public_notice": rights.get("public_notice"),
        "automated_floorplan_download_allowed": rights.get("automated_floorplan_download_allowed", False),
        "automated_floorplan_transformation_allowed": rights.get("automated_floorplan_transformation_allowed", False),
        "public_republication_allowed": rights.get("public_republication_allowed", False),
        "required_evidence": rights.get("required_evidence"),
        "operational_note": rights.get("operational_note"),
    }


@app.get("/api/skanska/stilla/latest")
def skanska_stilla_latest():
    payload = load_json_file(LATEST_FILE)
    rights = load_floorplan_rights()

    records = payload.get("records", [])
    pass_count = sum(
        item.get("identity_status") == "PASS"
        and item.get("evidence_status") == "PASS"
        for item in records
    )

    return {
        "status": "ok",
        "developer": payload.get("developer"),
        "project": payload.get("project"),
        "captured_at": payload.get("captured_at"),
        "count": payload.get("count", len(records)),
        "verified_pass_count": pass_count,
        "floorplan_rights_status": rights.get("status"),
        "records": records,
    }


@app.get("/api/skanska/stilla/apartments/{apartment_code}")
def skanska_stilla_apartment(apartment_code: str):
    payload = load_json_file(LATEST_FILE)
    rights = load_floorplan_rights()
    normalized_code = apartment_code.strip().upper()

    record = next(
        (
            item
            for item in payload.get("records", [])
            if str(item.get("apartment_code", "")).upper() == normalized_code
        ),
        None,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono lokalu {normalized_code}",
        )

    return {
        "status": "ok",
        "developer": payload.get("developer"),
        "project": payload.get("project"),
        "captured_at": payload.get("captured_at"),
        "floorplan_rights_status": rights.get("status"),
        "floorplan_rights_note": rights.get("operational_note"),
        "record": record,
    }


@app.get("/api/skanska/stilla/changes")
def skanska_stilla_changes():
    payload = load_json_file(CHANGES_FILE)

    return {
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "old_snapshot": payload.get("old_snapshot"),
        "new_snapshot": payload.get("new_snapshot"),
        "changes": payload.get("changes", []),
    }
