# CEN-KM Backend

Backend service for CEN-KM manual digitization and reconstruction workflows.

## Tech Stack
- Python + Flask
- pandas / numpy / lifelines

## Run
```bash
python app.py
```

Default port: `5000`

## Core Endpoints
- `POST /api/save_points`
- `POST /api/save_risk_table`
- `POST /api/reconstruct_v1`
- `POST /api/reconstruct_from_excel`
- `POST /api/reconstruct_with_overlay_from_excel`
- `GET  /api/ping`

## Static Serving
- `/` serves the built frontend
- `/static/*`, `/manifest.json`, `/asset-manifest.json`, `/favicon.ico`
- `/data/<filename>` serves generated artifacts from backend data directory
