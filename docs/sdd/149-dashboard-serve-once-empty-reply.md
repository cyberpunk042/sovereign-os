# SDD-149 — dashboard serve.py `--once`: fix the empty-reply race (killed daemon worker)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: `tests/nspawn/test_dashboard.sh` failed 2/33 (`curl GET /` + `GET /api/health` → rc=52, empty reply) — CI "layer 3 — stage acceptance (nspawn-style)" red on PR #118. Deterministic + pre-existing on `main`, **masked** until SDD-148 fixed `test_trinity` (the layer-3 job stops at the first failing nspawn test; trinity failed first, so dashboard never ran). Operator: "still failing" (re-sent the dashboard failure). Recover band (SDD-149 / E11.M149 per SDD-100).
> Derived from / extends: R225 (dashboard serve) + R250 (dashboard auth). §1g.

## Mission

Make `scripts/dashboard/serve.py --once` return a complete HTTP response so the layer-3 dashboard HTTP acceptance checks pass.

## Problem

`serve.py` runs on `ThreadingHTTPServer`. For `--once` it calls `srv.handle_request()`. With a **threading** server, `handle_request()` dispatches the request to a **worker thread and returns as soon as that thread is spawned — not when the response is written**. `main()` then reaches `finally: srv.server_close()` and returns; `ThreadingHTTPServer`'s workers are **daemon threads by default**, so process exit kills the worker **mid-render** before it flushes the response → the client gets an **empty reply** (`curl rc=52`).

It's **deterministic** (not a load flake): the full-page render (`gather_all()` — ~40 hardware cards, 3-4s of subprocess calls) is *always* still in flight when `main()` returns after `handle_request()`. Auth is not involved — it passes on loopback; the render path simply never completes. `--render-only` (direct render, no server) always worked, which is why the bug hid behind the HTTP path only.

Why it surfaced now: the layer-3 nspawn job stops at the first failing test. `test_trinity` failed first (SDD-148) and short-circuited the job before `test_dashboard` ran; with trinity green, the job reaches dashboard and the pre-existing empty-reply is exposed.

## Fix

`scripts/dashboard/serve.py` — in the `--once` branch, set `srv.daemon_threads = False` on the `ThreadingHTTPServer` before `handle_request()`. The worker is then non-daemon, so `server_close()` (`ThreadingMixIn.block_on_close`, default True) **joins** it and the response completes before exit. The normal `serve_forever()` path is untouched — it keeps running, so its daemon workers finish naturally; only the one-shot `--once` teardown needed the join.

Presentation/serving lifecycle only — no route, data, auth, or render change. R10212/SB-077 untouched.

## Verification

- `tests/nspawn/test_dashboard.sh` — **35/35 passed** (was 31/33; the 2 curl failures + the success-only follow-on assertions all now run), 3/3 consecutive runs, 0 curl failures.
- Sibling dashboard nspawn suites green: `test_dashboard_auth.sh` 14/14, `test_dashboard_grid.sh` 21/21, `test_dashboard_intel_cards.sh` 10/10, `test_dashboard_mobile.sh` 10/10, `test_dashboard_model_detail.sh` 13/13, `test_dashboard_modules_form.sh` 0 fails. The 3 that exercise the `--once` HTTP path (dashboard, dashboard_auth, dashboard_model_detail) all pass.
- Full pytest lint suite green.

## On completion

The layer-3 nspawn acceptance gate's dashboard HTTP checks pass; `serve.py --once` returns complete responses.

## Cross-references

- `scripts/dashboard/serve.py` (R225 serve, R250 auth). SDD-147 (oracle test-drift) + SDD-148 (trinity test-drift) — the two fixes that unmasked this. SDD-100 — band scheme.
