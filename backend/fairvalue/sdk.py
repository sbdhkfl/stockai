"""FAIRVALUE AI Python SDK.

Typed client for the FAIRVALUE REST API (docs/ARCHITECTURE.md §7). Reuses the
same pydantic schemas as the server, so responses are validated, not guessed.

Example
-------
    from fairvalue.sdk import FairValueClient

    client = FairValueClient(base_url="http://127.0.0.1:8000", api_key="secret")
    report = client.valuation("AAPL", price=270.0)
    print(report.reconciliation.base, report.reconciliation.low, report.reconciliation.high)
    for m in report.models:
        if m.applicable:
            print(m.model, m.value_per_share)

Every method raises :class:`SdkError` with the server's error code/message on
API errors (shape {"error": {"code", "message", "detail"}}).
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from fairvalue.core.schemas import (
    CompanyProfile,
    Fundamentals,
    HealthMetrics,
    GrowthAnalysis,
    RiskAssessment,
    ScenarioSet,
    ValuationExplanation,
    ValuationMultiples,
    ValuationReport,
)


class SdkError(RuntimeError):
    """An error returned by (or encountered while calling) the FAIRVALUE API."""

    def __init__(self, code: str, message: str, detail: str | None = None,
                 status: int | None = None):
        super().__init__(f"[{code}] {message}" + (f" ({detail})" if detail else ""))
        self.code = code
        self.message = message
        self.detail = detail
        self.status = status


def _parse_error(payload: Any) -> SdkError:
    try:
        err = payload["error"]
        return SdkError(err.get("code", "unknown"), err.get("message", ""),
                        err.get("detail"), status=None)
    except Exception:
        return SdkError("bad_response", f"unexpected error payload: {payload!r}")


class FairValueClient:
    """Synchronous typed client. ``transport`` is exposed for tests
    (httpx.ASGITransport over the FastAPI app — no live server needed)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000",
                 api_key: str | None = None, timeout: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        headers = {"X-API-Key": api_key} if api_key else {}
        self._http = httpx.Client(base_url=base_url, timeout=timeout,
                                  headers=headers, transport=transport)

    # ---------------- internals ----------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise SdkError("connection_error", f"request failed: {exc}") from exc
        if resp.status_code >= 400:
            try:
                raise _parse_error(resp.json()) from None
            except (ValueError, KeyError):
                raise SdkError("http_error", f"HTTP {resp.status_code}",
                               resp.text[:500], status=resp.status_code) from None
        return resp.json()

    @staticmethod
    def _model_or_error(data: Any, cls):
        if isinstance(data, dict) and "error" in data:
            raise _parse_error(data)
        return cls.model_validate(data)

    # ---------------- companies & statements ----------------

    def search(self, query: str, demo: bool = False) -> list[CompanyProfile]:
        data = self._request("GET", "/v1/companies/search",
                             params={"q": query, "demo": demo})
        return [CompanyProfile.model_validate(c) for c in data]

    def company(self, ticker: str, demo: bool = False) -> CompanyProfile:
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}", params={"demo": demo}),
            CompanyProfile)

    def statements(self, ticker: str, demo: bool = False) -> Fundamentals:
        """Normalized statements incl. provenance, missing concepts, conflicts."""
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}/statements",
                          params={"demo": demo}),
            Fundamentals)

    # ---------------- analysis ----------------

    def metrics(self, ticker: str, demo: bool = False) -> dict[str, Any]:
        data = self._request("GET", f"/v1/companies/{ticker}/metrics",
                             params={"demo": demo})
        return {"health": HealthMetrics.model_validate(data["health"]),
                "multiples": ValuationMultiples.model_validate(data["multiples"])}

    def health_metrics(self, ticker: str, demo: bool = False) -> HealthMetrics:
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}/health",
                          params={"demo": demo}),
            HealthMetrics)

    def risks(self, ticker: str, demo: bool = False) -> RiskAssessment:
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}/risks",
                          params={"demo": demo}),
            RiskAssessment)

    def valuation(self, ticker: str, *, price: float | None = None,
                  peers: list[str] | None = None, models: list[str] | None = None,
                  demo: bool = False) -> ValuationReport:
        params: dict[str, Any] = {"demo": demo}
        if price is not None:
            params["price"] = price
        if peers:
            params["peers"] = peers
        if models:
            params["models"] = models
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}/valuation", params=params),
            ValuationReport)

    def scenarios(self, ticker: str, demo: bool = False) -> ScenarioSet:
        data = self._request("POST", f"/v1/companies/{ticker}/scenarios",
                             json={"demo": demo})
        return self._model_or_error(data, ScenarioSet)

    def explain(self, ticker: str, demo: bool = False) -> ValuationExplanation:
        return self._model_or_error(
            self._request("GET", f"/v1/companies/{ticker}/explain",
                          params={"demo": demo}),
            ValuationExplanation)

    # ---------------- reports ----------------

    def reports(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/reports")

    def report(self, report_id: str) -> ValuationReport:
        return self._model_or_error(
            self._request("GET", f"/v1/reports/{report_id}"), ValuationReport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
