"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, Report } from "../../../lib/api";

function fmt(n: number | null | undefined, digits = 2, pct = false): string {
  if (n === null || n === undefined) return "—";
  return pct ? (n * 100).toFixed(1) + "%" : n.toFixed(digits);
}

export default function CompanyPage() {
  const params = useParams<{ ticker: string }>();
  const search = useSearchParams();
  const demo = search.get("demo") === "1";
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.valuation(params.ticker, demo).then(setReport).catch((e) => setError(String(e)));
  }, [params.ticker, demo]);

  if (error) return <div className="err">Failed to load valuation: {error}</div>;
  if (!report) return <p>Loading…</p>;
  const rec = report.reconciliation;
  const dcf = report.models.find((m) => m.model === "dcf");
  const price = report.market?.price ?? null;

  return (
    <>
      <div className="card">
        <h1>{report.company.name} ({report.company.ticker})</h1>
        <p className="muted">
          {report.company.sector ?? "sector unknown"} · schema {report.schema_version} ·
          generated {new Date(report.generated_at).toLocaleString()} ·
          market price {fmt(price)} · report <code>{report.report_id}</code>
        </p>
        {report.is_illustrative && (
          <div className="warn">ILLUSTRATIVE DEMO DATA — these are not real filings.</div>
        )}
        {rec.low !== null && rec.high !== null && (
          <>
            <div className="big">${rec.low.toFixed(2)} – ${rec.high.toFixed(2)}</div>
            <p>reconciled range · base <b>${rec.base?.toFixed(2)}</b>
              {price ? <> · market ${price.toFixed(2)} ({
                price >= rec.low && price <= rec.high
                  ? "within range" : "outside range"})</> : " · market price unavailable"}</p>
            <p className="muted">{rec.method}</p>
          </>
        )}
      </div>

      <div className="card">
        <h2>Model comparison</h2>
        <table>
          <thead><tr><th>Model</th><th>Value/share</th><th>Confidence</th><th>Suitability</th><th>Status</th></tr></thead>
          <tbody>
            {report.models.map((m) => (
              <tr key={m.model}>
                <td>{m.model}</td>
                <td>{m.applicable ? fmt(m.value_per_share) : "—"}</td>
                <td>{m.confidence ?? "—"}</td>
                <td>{fmt(m.suitability)}</td>
                <td>{m.applicable ? "✓"
                  : `excluded: ${m.excluded_reason ?? "not applicable"}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rec.notes.map((n, i) => <p key={i} className="muted">{n}</p>)}
      </div>

      {report.scenarios && (
        <div className="card">
          <h2>Bear / base / bull (DCF)</h2>
          <table>
            <thead><tr><th>Scenario</th><th>Value/share</th><th>WACC</th><th>Terminal growth</th><th>Notes</th></tr></thead>
            <tbody>
              {(["bear", "base", "bull"] as const).map((k) => {
                const s = report.scenarios![k];
                return (
                  <tr key={k}>
                    <td>{s.name}</td><td>{fmt(s.value_per_share)}</td>
                    <td>{fmt(Number(s.applied_assumptions["wacc"]) * 100, 1)}%</td>
                    <td>{fmt(Number(s.applied_assumptions["terminal_growth"]) * 100, 1)}%</td>
                    <td>{s.notes.join("; ") || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <h3>Sensitivity — value/share across WACC × terminal growth</h3>
          <SensitivityGrid points={report.scenarios.sensitivity} />
        </div>
      )}

      <div className="card">
        <h2>Financial health</h2>
        {report.health ? (
          <table><tbody>
            {Object.entries(report.health).filter(([k]) => k !== "notes").map(([k, v]) => (
              <tr key={k}><td>{k}</td>
                <td>{typeof v === "number" ? (k.includes("margin") || k === "roe" || k === "roic"
                  ? (v * 100).toFixed(1) + "%" : v.toFixed(2)) : String(v ?? "—")}</td></tr>
            ))}
          </tbody></table>
        ) : <p className="muted">Health metrics unavailable for this company (missing data is
          reported, never estimated).</p>}
      </div>

      <div className="card">
        <h2>Risk analysis</h2>
        {report.risks ? (
          <>
            <p>Altman Z: <b>{fmt(report.risks.altman_z)}</b> ({report.risks.altman_zone ?? "not computable"})
              — a screening statistic, not a bankruptcy probability; not calibrated for banks/insurers.</p>
            <ul>{report.risks.flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
            <p className="muted">Data gaps: {report.risks.data_gaps.join("; ") || "none"}</p>
          </>
        ) : <p className="muted">Risks unavailable.</p>}
      </div>

      <div className="card">
        <h2>Assumptions, derivation & data sources</h2>
        {report.models.filter((m) => m.applicable).map((m) => (
          <details key={m.model}>
            <summary><b>{m.model}</b> — {fmt(m.value_per_share)}/share</summary>
            <p><code>{m.formula}</code></p>
            <ol>{m.steps?.map((s, i) => <li key={i}>{s}</li>)}</ol>
            {m.limitations && <p className="muted">Limitations: {m.limitations.join(" ")}</p>}
            {m.warnings && m.warnings.length > 0 && <div className="warn">
              {m.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>}
          </details>
        ))}
        <h3>Data quality</h3>
        <p className="muted">Missing concepts (reported, never filled):
          {report.data_quality.missing.join(", ") || " none"}</p>
        {report.data_quality.conflicts.length > 0 && (
          <p className="muted">Restatement conflicts: {report.data_quality.conflicts.length} recorded
            (latest filing wins; original values retained in statements view).</p>)}
        <details><summary>Provenance ({report.data_quality.sources.length} sources)</summary>
          <pre style={{ fontSize: 11, overflow: "auto" }}>{JSON.stringify(report.data_quality.sources, null, 1)}</pre>
        </details>
        {dcf?.assumptions && (
          <details><summary>DCF assumptions echo</summary>
            <pre style={{ fontSize: 11 }}>{JSON.stringify(dcf.assumptions, null, 1)}</pre>
          </details>)}
      </div>
      <p className="muted">All figures are estimates conditional on the displayed assumptions.
        Analysis only — not investment advice.</p>
    </>
  );
}

function SensitivityGrid({ points }: { points: Report["scenarios"] extends null ? never :
  NonNullable<Report["scenarios"]>["sensitivity"] }) {
  const waccs = [...new Set(points.map((p) => p.wacc))].sort((a, b) => a - b);
  const gs = [...new Set(points.map((p) => p.terminal_growth))].sort((a, b) => a - b);
  const cell = (w: number, g: number) => {
    const p = points.find((x) => x.wacc === w && x.terminal_growth === g);
    return p?.value_per_share;
  };
  return (
    <table>
      <thead><tr><th>WACC \\ g</th>{gs.map((g) => <th key={g}>{(g * 100).toFixed(2)}%</th>)}</tr></thead>
      <tbody>
        {waccs.map((w) => (
          <tr key={w}><td>{(w * 100).toFixed(2)}%</td>
            {gs.map((g) => <td key={g}>{fmt(cell(w, g))}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}
