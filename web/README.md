# FAIRVALUE AI Dashboard (Next.js)

Renders **real data from the FAIRVALUE REST API** — no decorative or fake data.
Every screen surfaces assumptions, limitations, missing data and provenance the
engine reports.

## Run

```bash
cd web
npm install
# against a live API:
NEXT_PUBLIC_FAIRVALUE_API=http://127.0.0.1:8000 npm run dev
# offline demo companies (clearly labeled illustrative):
#  open http://localhost:3000, tick "demo data", search AUR / HELI / CRVN
```

Requires the API running (`uvicorn api.main:app` from `backend/`).

## Screens

- `/` — company search (live EDGAR or demo), report history loader
- `/company/[ticker]` — overview: reconciled value range vs market price,
  model comparison (incl. exclusions with reasons), bear/base/bull + WACC×g
  sensitivity grid, financial health, risk analysis, per-model derivation steps,
  assumptions echo, data-quality (missing concepts, restatement conflicts,
  provenance sources)

## Honest limitations

- The API persists reports in memory in this MVP; the report-history panel only
  lists reports created in the same server session (DB persistence exists in
  `backend/fairvalue/db/` and needs API wiring by the Lead).
- Prices come from Stooq and may be unavailable; the dashboard shows "—" rather
  than guessing.
