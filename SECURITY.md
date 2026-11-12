# Security policy

## Reporting a vulnerability

- **Preferred:** GitHub → *Security* → *Report a vulnerability* (private
  advisory) once the repository is public. Enable *Private vulnerability
  reporting* in repository settings.
- Until then: contact the maintainers privately. **Do not open a public issue
  for security-relevant reports.**

You will get an acknowledgment and an honest status; fixes land on the
release branch with regression tests.

## Supported versions

The default branch of the public repository is the only supported line.
There are no versioned releases yet.

## Design notes (what protects you)

- **API auth:** optional `X-API-Key` (`FAIRVALUE_API_KEY`), compared with
  `hmac.compare_digest` (constant time). Deploy behind TLS — the key travels
  in a header.
- **Rate limiting:** per-client request window (`FAIRVALUE_RATE_LIMIT`,
  `FAIRVALUE_RATE_WINDOW_S`), with a bounded client map.
- **CORS:** explicit origin allow-list (`FAIRVALUE_CORS_ORIGINS`), never `*`.
- **Error contract:** failures return structured `{"error": {code, message,
  detail}}`; upstream provider failures surface as 502 provider errors without
  leaking internals or stack traces.
- **No secrets in the repository:** no `.env` files, keys, tokens or
  connection strings are committed (`.env*`, `*.db`, `*.sqlite*` are
  git-ignored). Full git history was scanned with gitleaks — zero findings.
- **Dependency audits:** `pip-audit` (Python) and `npm audit` (dashboard) both
  report zero known vulnerabilities at release time; CI does not yet
  re-run them automatically.
- **MCP server** runs over stdio (local process, no network listener) and
  returns structured errors; it executes no arbitrary commands.
- **No LLM in the engine:** valuation math is deterministic Python — no
  prompt-injection surface inside calculations.

## Operational guidance for deployers

- Set a long random `FAIRVALUE_API_KEY`; rotate it if exposed.
- Restrict `FAIRVALUE_CORS_ORIGINS` to your real dashboard origin.
- Keep `FAIRVALUE_DB_URL` credentials out of git (environment only).
- SEC EDGAR asks for a descriptive User-Agent with contact info — set
  `SEC_EDGAR_UA` for production traffic volumes.
- This software is research tooling, provided under MIT **without warranty**;
  it is not investment advice (see README).
