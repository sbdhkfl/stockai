"use client";
import { useState } from "react";
import { api, CompanyProfile } from "../lib/api";

export default function Home() {
  const [q, setQ] = useState("");
  const [demo, setDemo] = useState(true);
  const [results, setResults] = useState<CompanyProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function doSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setResults(null);
    try { setResults(await api.search(q, demo)); }
    catch (err) { setError(String(err)); }
  }

  return (
    <>
      <div className="card">
        <h1>Company search</h1>
        <form onSubmit={doSearch} style={{ display: "flex", gap: 8 }}>
          <input style={{ flex: 1 }} value={q} placeholder="Ticker or company name (e.g. AAPL)"
            onChange={(e) => setQ(e.target.value)} required />
          <label style={{ fontSize: 13, alignSelf: "center" }}>
            <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} />
            {" "}demo data (offline, illustrative)
          </label>
          <button>Search</button>
        </form>
        <p className="muted">
          Real filings come from SEC EDGAR; demo mode returns clearly-labeled illustrative data.
        </p>
        {error && <div className="err">{error}</div>}
        {results && (
          <table>
            <thead><tr><th>Ticker</th><th>Name</th><th>Sector</th><th>Industry</th><th></th></tr></thead>
            <tbody>
              {results.map((c) => (
                <tr key={c.ticker}>
                  <td>{c.ticker}</td><td>{c.name}</td><td>{c.sector ?? "—"}</td>
                  <td>{c.industry ?? "—"}</td>
                  <td><a href={`/company/${c.ticker}${demo ? "?demo=1" : ""}`}>Open →</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="card">
        <h2>Saved reports</h2>
        <SavedReports />
      </div>
    </>
  );
}

function SavedReports() {
  const [rows, setRows] = useState<{ report_id: string; ticker: string; generated_at: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <button onClick={async () => {
        try { setRows(await api.reports()); } catch (e) { setError(String(e)); }
      }}>Load report history</button>
      {error && <div className="warn">{error}</div>}
      {rows && (rows.length === 0
        ? <p className="muted">No reports persisted yet (valuation responses carry report_id;
          persistence requires the DB-backed API configuration).</p>
        : <table><tbody>
          {rows.map((r) => (
            <tr key={r.report_id}><td>{r.ticker}</td><td>{r.generated_at}</td>
              <td><code>{r.report_id}</code></td></tr>))}
        </tbody></table>)}
    </>
  );
}
