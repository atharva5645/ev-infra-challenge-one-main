# EV Infra Map India

A hackathon prototype for exploring India's public EV charging-station directory and transparent infrastructure planning scenarios.

## Project layout

- `frontend/` — React, Vite, TypeScript and Leaflet application.
- `backend/` — FastAPI API proxy and planning calculation services.
- `database/` — PostgreSQL-compatible schema and illustrative seed-data foundation; it is not connected to the API yet.

## Run locally

Start the backend in one terminal:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is served at `http://localhost:5173`; the backend health check is at `http://127.0.0.1:8000/health`.

## Data scope

Charging-station records are served through the EV Charging Stations API and attributed to a BEE dataset snapshot dated 26 October 2025. This is a directory snapshot, not live charger availability. Dashboard page statistics and illustrative planning calculations are labelled with their scope and assumptions. No database connection is configured.
