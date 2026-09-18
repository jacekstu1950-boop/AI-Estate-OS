import json

from fastapi.testclient import TestClient

import api.app as api_app


client = TestClient(api_app.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_served(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text("<html><body>AI-Estate-OS</body></html>", encoding="utf-8")
    monkeypatch.setattr(api_app, "WEB_INDEX", index)

    response = client.get("/")

    assert response.status_code == 200
    assert "AI-Estate-OS" in response.text
    assert response.headers["cache-control"].startswith("no-store")


def test_latest_returns_verified_snapshot(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "developer": "Skanska",
                "project": "Stilla",
                "captured_at": "2026-09-18T17:24:37",
                "count": 2,
                "records": [
                    {
                        "apartment_code": "BA0005",
                        "identity_status": "PASS",
                        "evidence_status": "PASS",
                    },
                    {
                        "apartment_code": "BA0122",
                        "identity_status": "PASS",
                        "evidence_status": "PASS",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(api_app, "LATEST_FILE", latest)

    response = client.get("/api/skanska/stilla/latest")
    body = response.json()

    assert response.status_code == 200
    assert body["developer"] == "Skanska"
    assert body["project"] == "Stilla"
    assert body["count"] == 2
    assert body["verified_pass_count"] == 2
    assert body["floorplan_rights_status"] == "UNKNOWN"


def test_latest_returns_503_when_snapshot_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        api_app,
        "LATEST_FILE",
        tmp_path / "missing.json",
    )

    response = client.get("/api/skanska/stilla/latest")

    assert response.status_code == 503


def test_changes_returns_latest_diff(tmp_path, monkeypatch):
    changes = tmp_path / "changes_latest.json"
    changes.write_text(
        json.dumps(
            {
                "status": "OK",
                "old_snapshot": "old.json",
                "new_snapshot": "new.json",
                "summary": {
                    "ADDED": 1,
                    "REMOVED": 0,
                    "CHANGED": 1,
                    "UNCHANGED": 4,
                },
                "changes": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(api_app, "CHANGES_FILE", changes)

    response = client.get("/api/skanska/stilla/changes")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "OK"
    assert body["summary"]["ADDED"] == 1
    assert body["summary"]["CHANGED"] == 1
