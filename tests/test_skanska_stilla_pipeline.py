from adapters import skanska_stilla_pipeline as pipeline


def make_record(code, identity="PASS", evidence="PASS"):
    return {
        "apartment_code": code,
        "identity_status": identity,
        "evidence_status": evidence,
    }


def test_summarize_verification():
    result = pipeline.summarize_verification([
        make_record("A"),
        make_record("B", identity="FAIL", evidence="UNKNOWN"),
        make_record("C", identity="PASS", evidence="UNKNOWN"),
    ])

    assert result == {
        "PASS": 1,
        "FAIL": 1,
        "UNKNOWN": 1,
    }


def test_pipeline_blocks_snapshot_when_validation_not_clean(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "discover_apartment_codes",
        lambda headless=True: [
            {"apartment_code": "BA0005"},
            {"apartment_code": "BA0123"},
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "verify_discovered_apartments",
        lambda records, headless=True: [
            make_record("BA0005"),
            make_record("BA0123", identity="FAIL", evidence="UNKNOWN"),
        ],
    )

    called = {"snapshot": False}

    def forbidden_save(*args, **kwargs):
        called["snapshot"] = True
        raise AssertionError("save_snapshot nie powinien zostać wywołany")

    monkeypatch.setattr(pipeline, "save_snapshot", forbidden_save)

    result = pipeline.run_pipeline(headless=True)

    assert result["status"] == "BLOCKED"
    assert result["verification"] == {
        "PASS": 1,
        "FAIL": 1,
        "UNKNOWN": 0,
    }
    assert called["snapshot"] is False


def test_pipeline_runs_snapshot_and_diff_when_all_pass(monkeypatch):
    discovered = [
        {"apartment_code": "BA0005"},
        {"apartment_code": "BA0122"},
    ]
    verified = [
        make_record("BA0005"),
        make_record("BA0122"),
    ]

    monkeypatch.setattr(
        pipeline,
        "discover_apartment_codes",
        lambda headless=True: discovered,
    )
    monkeypatch.setattr(
        pipeline,
        "verify_discovered_apartments",
        lambda records, headless=True: verified,
    )
    monkeypatch.setattr(
        pipeline,
        "build_snapshot",
        lambda records: {"records": records},
    )
    monkeypatch.setattr(
        pipeline,
        "save_snapshot",
        lambda snapshot, directory: (
            directory / "stilla_test.json",
            directory / "latest.json",
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "compare_latest_two",
        lambda directory: {
            "status": "OK",
            "summary": {
                "ADDED": 0,
                "REMOVED": 0,
                "CHANGED": 0,
                "UNCHANGED": 2,
            },
            "changes": [],
        },
    )
    monkeypatch.setattr(
        pipeline,
        "save_diff",
        lambda result: pipeline.SNAPSHOT_DIR / "changes_latest.json",
    )

    result = pipeline.run_pipeline(headless=True)

    assert result["status"] == "OK"
    assert result["discovered_count"] == 2
    assert result["verification"] == {
        "PASS": 2,
        "FAIL": 0,
        "UNKNOWN": 0,
    }
    assert result["diff"]["summary"]["UNCHANGED"] == 2
