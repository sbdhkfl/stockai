# FAIRVALUE AI

Financially defensible, mathematically tested stock valuation engine.

- **Quant Agent** owns `backend/fairvalue/` (pure financial library) and `docs/` methodology.
- **OpenCode** owns architecture and integration (see `docs/AGENT_TASKS.md`).
- Architecture decisions in `docs/ARCHITECTURE_PROPOSAL.md` are **PROPOSED**, not final.

## Quick start

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -q        # 60+ hand-verified known-answer tests
uvicorn api.main:app --reload     # API skeleton
```

## Core guarantee

Every valuation explains *what* was calculated, *how*, with *which data*,
*which formulas*, and *which assumptions*. See `docs/FINANCIAL_METHODOLOGY.md`.
