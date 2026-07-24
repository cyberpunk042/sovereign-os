# SDD-525 — Token-law coverage: operator custom-scenario read-compute

> Status: active · Mandate: **E11.M525** (control-bits band 500–599)
>
> Cross-link: the v2 of SDD-511's coverage heatmap — its named non-goal (*"Operator-supplied sources/vocab (a v2 input form)"*). The twenty-fourth SDD in the control-bits band.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"all of these, a big PR"*).

## Mission

The token-law coverage panel (SDD-511) rendered only a **built-in sample scenario**; the daemon deliberately `405`d POST ("read-only … drive custom fuses from the CLI"). SDD-511's non-goals named the fix: a **v2 input form** so an operator can see per-layer coverage for *their own* vocab + sources. This ships it — as a **read-compute**, preserving the panel's no-mutation guarantee.

## Design

### The reversal is a read-compute, not a mutation (R10212)

The 405 was a *no-POST* stance, not a *no-mutation* one. The gateway `token-law/fuse` route the coverage derives from is **non-mutating** — it computes allowed-token counts from `(vocab, sources)` and changes no server state. So accepting a POST that runs a custom fuse is still R10212-consistent: a read-compute, not a write. The panel's standing rule shifts from "read-only" to "read-compute (no server mutation)".

### The daemon (`scripts/operator/token-law-coverage-api.py`)

- `compute_coverage(vocab=None, layer_specs=None)` is parameterized — defaults to the SAMPLE scenario (the GET feed); a custom `(vocab, layer_specs)` drives an operator scenario. `scenario` in the payload reports `"sample"` vs `"custom"`.
- `do_POST` on `/api/token-law-coverage/coverage` parses `{vocab, layers}` (vocab = non-empty list of strings; layers = list of `{name, source}`), validates (bad input → `400`, never silently served), and returns `compute_coverage(vocab, specs)`. It only ever calls the non-mutating fuse route; no `do_PUT`/`do_DELETE`; no file writes.

### The panel (`webapp/token-law-coverage/index.html`)

A `<details>` "Custom scenario (read-compute)" section: a vocab textarea + a layers-JSON textarea + a Compute button that POSTs `{vocab, layers}` to the **same** coverage endpoint and re-renders via the existing `renderCoverage` (which already reads `scenario`). Validation errors show inline; an offline gateway honest-degrades via `renderOffline`. Single same-origin endpoint (the R10212 fetch-shape lint still holds).

### Honest scope

- The custom fuse still runs on the gateway's checkpoint-free `token-law/fuse` route — no model needed, honest-degrade when the gateway is down (SDD-511 invariant, unchanged).
- The panel offers a minimal form (vocab + layers JSON); a richer per-layer source builder is a UX follow-up, not a capability gap.

## What shipped

- **`scripts/operator/token-law-coverage-api.py`** — parameterized `compute_coverage`; `do_POST` custom-scenario read-compute (validates → `400` on bad input).
- **`webapp/token-law-coverage/index.html`** — the custom-scenario form + POST handler (reuses `renderCoverage`); the standing-rule meta shifts to "read-compute".
- **`tests/lint/test_token_law_heatmap_webapp_contract.py`** — the read-only assertion becomes a **read-compute** contract (POST computes custom coverage; no mutating verbs; `400` on bad input).
- Registration: SDD-525 + INDEX row 525 + mandate **E11.M525** + catalog regen + context `sdd files` (part of the 232→235 batch).

## Non-goals / roadmap

- A richer source-builder UI (per-layer typed inputs vs a JSON textarea).
- Persisting / sharing custom scenarios (would introduce state — deliberately out, to keep the panel a pure read-compute).

## References

- The predecessor: `docs/sdd/511-token-law-mask-coverage-heatmap.md` (the sample-scenario panel; its non-goal named this).
- The surfaces: `scripts/operator/token-law-coverage-api.py`, `webapp/token-law-coverage/index.html`.
- The guard: `tests/lint/test_token_law_heatmap_webapp_contract.py`.
