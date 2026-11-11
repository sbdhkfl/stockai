"""Thin FastAPI adapter over the fairvalue engine (PROPOSED contract, v0).

The API owns no math: it converts request models into engine calls.
Run: uvicorn api.main:app --reload   (from backend/)
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fairvalue.valuation.dcf import dcf_fcff
from fairvalue.valuation.ddm import gordon_ddm
from fairvalue.analysis.risk import altman_z
from fairvalue.analysis.scenario import DCFInputs, run_all_scenarios, sensitivity_grid
from fairvalue.errors import FairValueError, NotMeaningfulError, NotSuitableError

app = FastAPI(title="FAIRVALUE AI Financial Engine", version="0.1.0")


class DCFRequest(BaseModel):
    fcff: list[float] = Field(..., min_length=1)
    wacc: float
    terminal_growth: float
    net_debt: float
    diluted_shares: float


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/valuation/dcf")
def valuation_dcf(req: DCFRequest):
    try:
        r = dcf_fcff(req.fcff, req.wacc, req.terminal_growth,
                     req.net_debt, req.diluted_shares)
    except (FairValueError, NotMeaningfulError, NotSuitableError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"assumptions_echoed": req.model_dump(),
            "enterprise_value": r.enterprise_value,
            "equity_value": r.equity_value,
            "value_per_share": r.value_per_share,
            "pv_explicit": r.pv_explicit,
            "pv_terminal_value": r.pv_terminal_value,
            "terminal_value": r.terminal_value}


class DDMRequest(BaseModel):
    d0: float
    r: float
    g: float


@app.post("/valuation/ddm")
def valuation_ddm(req: DDMRequest):
    try:
        return {"value": gordon_ddm(req.d0, req.r, req.g)}
    except FairValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class AltmanRequest(BaseModel):
    working_capital: float
    total_assets: float
    retained_earnings: float
    ebit: float
    market_equity: float
    total_liabilities: float
    sales: float
    sector: str = "manufacturing"


@app.post("/risk/altman-z")
def risk_altman(req: AltmanRequest):
    try:
        r = altman_z(req.working_capital, req.total_assets, req.retained_earnings,
                     req.ebit, req.market_equity, req.total_liabilities,
                     req.sales, req.sector)
    except FairValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"z_score": r.z, "zone": r.zone, "warnings": r.warnings}


@app.post("/scenario/all")
def scenarios(req: DCFRequest):
    try:
        inputs = DCFInputs(**req.model_dump())
        return run_all_scenarios(inputs)
    except FairValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
