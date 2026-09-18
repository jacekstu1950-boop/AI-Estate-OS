import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

APP_VERSION = "0.2.1"
SNAPSHOT_DIR = Path("snapshots") / "skanska_stilla"
LATEST_FILE = SNAPSHOT_DIR / "latest.json"
CHANGES_FILE = SNAPSHOT_DIR / "changes_latest.json"
WEB_INDEX = Path("web") / "index.html"

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


@app.get("/", include_in_schema=False)
def frontend():
    if not WEB_INDEX.exists():
        raise HTTPException(status_code=503, detail="Brak pliku web/index.html")
    return FileResponse(
        WEB_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-estate-os-api",
        "version": APP_VERSION,
    }


@app.get("/api/skanska/stilla/latest")
def skanska_stilla_latest():
    payload = load_json_file(LATEST_FILE)

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
        "floorplan_rights_status": "UNKNOWN",
        "records": records,
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
