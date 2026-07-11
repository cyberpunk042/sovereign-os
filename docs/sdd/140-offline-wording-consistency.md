# SDD-140 — Phase 4: honest-offline card wording consistency

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the Phase-4 visual-consistency recon found the "the <X> daemon is unreachable — … Nothing is fabricated (SB-077)." honest-offline scaffold cards (the SDD-111/113/115 always-visible pattern) had drifted in wording across the 3 panels that use them: d-24 says "… populates when it's reachable" (the canonical exemplar), d-23 said "… will list here when it's reachable", d-25 said "… populate here when it's reachable" — same honest message, three phrasings, none pinned by a lint. (The recon also confirmed the token-standardization path is a trap: no spacing/type scale exists to standardize toward, and any color-token normalization collides with the SDD-040 palette lint's `--good/--bad` vs the grammar doc's `--ok/--danger` — that reconciliation is its own SDD-040 evolution round.) Recover band (SDD-140 / E11.M140 per SDD-100).
> Derived from / extends: SDD-111/113/115 (the always-visible honest-offline card pattern). §1g / SB-077.

## Mission

Converge the honest-offline daemon-unreachable scaffold cards to one canonical phrasing and pin it, so the operator sees consistent "why is this empty, and it's honest" language everywhere a daemon is down.

## Grounded design (CSS-copy-only, 2 panels + 1 lint)

Canonical form (d-24 is the exemplar, unchanged): **`the <X> daemon is unreachable — <what> populate[s] when it's reachable. Nothing is fabricated (SB-077).`**

- `d-23-models-catalog` — "the registry (…) **will list here** when it's reachable" → "the registry (…) **populates** when it's reachable".
- `d-25-selfdef-management` — "… the per-domain panels (D-13..D-18) **populate here** when it's reachable" → "… **populate** when it's reachable" (drop the stray "here"; the compound subject keeps the plural verb).
- `d-24-cpu-features` — already canonical, untouched (the reference).

The "Nothing is fabricated (SB-077)." honesty clause + the "when it's reachable" promise are the load-bearing SB-077 invariants; only the verb phrasing was drifting.

## Scope note

Only the 3 true scaffold cards are in scope. "daemon is unreachable" also appears in 6 other panels as **assistant hover-intel prose** ("… daemon is unreachable;") or **code comments** — a different context, correctly left alone (the lint targets only the card, identified by co-occurrence of the lead + the SB-077 honesty clause). The 18 data-source `#data-source-banner` phrasings (2 patterns) + master-dashboard's lint-pinned section cards ("route table unreachable" etc.) are a **distinct** empty-state element — a noted follow-up, not this SDD.

## R10212 / SB-077 preserved

Visible-copy only. No behaviour/data/runtime change. The SB-077 honesty clause is preserved (strengthened — now uniform). R10212 untouched.

## Verification

- NEW `tests/lint/test_offline_wording_consistency.py`: (1) the 3 scaffold-card panels end their card with the canonical `when it's reachable. Nothing is fabricated (SB-077).`; (2) no panel anywhere contains the banned drift phrasings `will list here` / `populate here`.
- Playwright (file://, daemon naturally unreachable → the offline scaffold renders): d-23 / d-24 / d-25 all show the canonical tail, **no drift, 0 page errors**.
- Full `make test` green.

## On completion

Remaining Phase 4 (follow-up): converge the 18 data-source banner phrasings (2 patterns → 1) + align master-dashboard's section-scaffold cards (updating `test_master_dashboard_resilience.py`'s pinned literals in lockstep); optionally an SDD-040 evolution round to reconcile the `--good/--bad` vs `--ok/--danger` token vocabularies before any spacing/type-scale work.

## Cross-references

- SDD-111/113/115 (honest-offline card origin); `webapp/{d-23-models-catalog,d-24-cpu-features,d-25-selfdef-management}/index.html`; `webapp/_shared/design-grammar.md` (token/button canon). SDD-100 — band scheme.
