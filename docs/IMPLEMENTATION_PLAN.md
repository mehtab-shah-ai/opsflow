# OpsFlow AI implementation plan

Goal: build an interview-ready operations copilot demonstrating the exact Grace Facility Service JD: internal tools, spreadsheet automation, practical cloud AI, troubleshooting and business communication.

Source: https://in.indeed.com/viewjob?jk=318fcf27fc99af16 (read 27 September 2026). All facility data and business rules are synthetic demonstrations, not company disclosures.

Architecture: React/TypeScript/Vite client; FastAPI single process; bounded asynchronous job queue; SQLite WAL repository; immutable source bytes and rows; versioned, explicitly approved cleaning. Deterministic quality, rules and analytics feed a constrained AI tool planner. Groq then Gemini sequential fallback; no generated code execution.

Design: warm ivory canvas, white panels, deep forest/teal brand, subtle lime highlights, crisp typography, compact sidebar and generous content spacing. A visible data journey connects upload, validation, review and decisions. Every navigation entry is functional. Charts derive from schema and computed aggregates.

## Work sequence

- [ ] Ingestion: write rejection and parsing tests; implement bounded CSV/XLSX/XLS/PDF extraction, table selection, safe public Sheets connector. Preserve raw files and reject ambiguous structural loss.
- [ ] Domain: test quality rules, ambiguity, immutability, duplicate flags, numeric normalization and deterministic metrics; implement analysis, cleaning preview/apply and schema-driven chart specifications.
- [ ] Service: test isolated sessions, queue limits, idempotency, version conflicts and exports; implement repository, jobs, endpoints and audited transactions.
- [ ] AI: test allowlisted plans, malformed JSON, fallback, 429 circuit breaking; implement providers, aggregate-only context, exact-fact summary and safe chat tools.
- [ ] Interface: build all nine workspace sections, immediate synthetic preview, multi-file uploads, live jobs, selection, cleaning drawer, reports and system diagnostics.
- [ ] Delivery: generate seeded demo CSV/XLSX/PDF, test API end-to-end and hostile files, build/lint frontend, inspect desktop/tablet/mobile, independent review and fixes, Render config and interview guide.

## Verification focus

1. Parallel uploads are bounded and failures do not corrupt other jobs.
2. Cleaning cannot delete rows, alter originals, replay a stale version, or accept invented issues.
3. Duplicate attendance cannot inflate staffing metrics; missing dates and sites remain visible.
4. Provider failure never prevents analysis/export; uploaded instructions never become tool authority.
5. Reset/refresh resumes real jobs or explains expired runtime; no fake readiness or metrics.

## Decisions

The user explicitly asked for autonomous implementation without plan/design approval pauses. Execute inline; retain a final independent review. Existing workspace has only a private environment file, so no separate Git checkout is needed. Do not publish until deployment credentials/target are available. Demo persistence is ephemeral on Render free service. File limits and bounded workloads are enforced; no claim of handling every possible file or unlimited load.
