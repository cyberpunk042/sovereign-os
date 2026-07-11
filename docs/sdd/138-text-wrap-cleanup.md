# SDD-138 — Phase 4: text-wrap cleanup (word-break:break-all → overflow-wrap:anywhere)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the SDD-137 responsive sweep flagged `word-break:break-all` in 4 panels as a noted follow-up. `word-break:break-all` breaks a string at ANY character, ALWAYS — so a long hash or log token is chopped mid-word even when it would have fit, and on the two `<pre>` panels it pairs contradictorily with `overflow-x:auto` (the forced wrap means the horizontal scroller never engages). The graceful idiom is `overflow-wrap:anywhere`. Recover band (SDD-138 / E11.M138 per SDD-100).
> Derived from / extends: SDD-137 (responsive grid sweep — same beauty/UX stream). §1g.

## Mission

Replace aggressive mid-word `word-break:break-all` with `overflow-wrap:anywhere` so long unbreakable strings (hashes, log lines) wrap **only when they would overflow** — never chopped mid-word gratuitously — and the element's min-content can shrink (so it never forces a grid to overflow, pairing with the SDD-137 `minmax(0,1fr)` work).

## Grounded design (CSS-only, 4 panels)

- `d-05-traces` — `.detail dd{ … word-break:break-all }` → `overflow-wrap:anywhere` (trace hash/value column).
- `d-16-audit` — `.hash{ … word-break:break-all }` → `overflow-wrap:anywhere` (audit-chain hashes).
- `global-history` — `pre{ … overflow-x:auto; white-space:pre-wrap; word-break:break-all }` → `overflow-wrap:anywhere` (the `pre-wrap` + `overflow-wrap:anywhere` combo wraps long tokens gracefully; `overflow-x:auto` stays as the fallback).
- `network-edge` — identical `pre{…}` fix.

## Why `overflow-wrap:anywhere` (not `break-word`)

`overflow-wrap:break-word` breaks an overflowing word but does NOT let the element's min-content shrink — so inside a grid track it can still force overflow. `overflow-wrap:anywhere` breaks on overflow AND shrinks min-content, which is exactly what the SDD-137 `minmax(0,1fr)` tracks need to stay contained.

## R10212 / SB-077 preserved

CSS-only presentation. No behaviour/data/runtime change; nothing fabricated. R10212 untouched.

## Verification

- NEW `tests/lint/test_text_wrap_contract.py`: (1) no panel keeps `word-break:break-all` anywhere in its CSS; (2) the 4 cleaned panels carry `overflow-wrap:anywhere`.
- Playwright (viewport 1100, `body.so-assist-open`, a 240-char unbroken hash-like token injected into each panel's target element): all 4 → **page-overflow 0px · element-overflow 0px · 0 page errors** — the long token wraps within its container instead of overflowing.
- Full `make test` green.

## On completion

Remaining Phase 4 (each a focused SDD/PR): the `ux-design-audit` six-dimension checklist sweep (action-budget / discoverable / recoverable / next-step / operator-named / readable-30s); spacing/typography/empty-state polish.

## Cross-references

- SDD-137 (responsive grid sweep — flagged this follow-up); `webapp/{d-05-traces,d-16-audit,global-history,network-edge}/index.html`. SDD-100 — band scheme.
