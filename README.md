# 🏋️ Gym Tracker

Personal fitness tracking dashboard built on top of Strong app exports.

## Stack
- **Python** — data engineering / ingestion
- **SQLite** — local database (will migrate to Postgres in phase 2)
- **Streamlit** — dashboard UI
- **Pandas** — CSV processing

## Project Structure

```
gym-tracker/
├── data/
│   └── exports/          # Drop your Strong CSV exports here
├── src/
│   ├── db/
│   │   └── schema.py     # DB setup and connection
│   ├── ingestion/
│   │   └── ingest.py     # Strong CSV → SQLite pipeline
│   └── dashboard/
│       └── app.py        # Streamlit dashboard
├── tests/
├── requirements.txt
└── .gitignore
```

## Setup

```bash
# 1. Clone the repo and create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialise the database
python src/db/schema.py

# 4. Drop your Strong export CSV into data/exports/ then run ingestion
python src/ingestion/ingest.py

# 5. Launch the dashboard
streamlit run src/dashboard/app.py
```

## Exporting from Strong

Strong app → Profile tab → Settings (top right) → Export Data → CSV  
Drop the exported file into `data/exports/` — the ingestion script will pick it up.

## Roadmap

- [x] Phase 1 — Local pipeline + Streamlit dashboard
- [ ] Phase 2 — Postgres + deploy to web (Railway/Render)
- [ ] Phase 3 — Programme tracking (planned vs actual)
- [ ] Phase 4 — Automate Strong export ingestion
