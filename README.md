# AI-Estate-OS

Minimal MVP pipeline for verified developer-apartment data.

## Skanska Stilla pipeline

Run the verified discovery -> validation -> snapshot -> diff flow:

```bat
python -m adapters.skanska_stilla_pipeline
```

## API

Install dependencies:

```bat
python -m pip install -r requirements-dev.txt
```

Start the local API:

```bat
python -m uvicorn api.app:app --reload
```

Open:

- Health: `http://127.0.0.1:8000/health`
- Latest verified Stilla snapshot: `http://127.0.0.1:8000/api/skanska/stilla/latest`
- Latest Stilla changes: `http://127.0.0.1:8000/api/skanska/stilla/changes`
- Interactive API docs: `http://127.0.0.1:8000/docs`

The API reads runtime snapshot files from `snapshots/skanska_stilla/`.
Floor-plan rights remain a separate gate and are not promoted to PASS by this API.
