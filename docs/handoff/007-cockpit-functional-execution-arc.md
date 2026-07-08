# Handoff 007 — Cockpit functional-execution arc (SDD-047, R10274) + branch-gate

> **Status**: Phase 0 shipped + verified; Phases 1-3 gated on one operator decision
> **Last updated**: 2026-07-08
> **Owner**: sovereign-os core
> **Predecessor handoff**: 006-verbatim-preservation-arc.md

## What this arc was

Operator directive 2026-07-08 (verbatim, sacrosanct):

> **"we now have a sudoer strategy, we will fix everything that is a manual
> command so that the manual command is only the alternative but we will
> otherwise do the features functional from the panels / dashboard, this mean
> all existing one including the new ones ... This is massive evolution take
> your time to do it well."**

Make the cockpit panels **functionally execute** controls instead of only
copying an MS003-signed CLI verb to the clipboard — the functional realization
of **R10274** (the sanctioned signed-mutation-proxy path). **R10212 stays**: the
web still never *arbitrarily* mutates; it executes only allowlisted, validated,
confirmed, audited verbs, and the selfdef-owned controls stay a signed proxy.

Preceding the same branch: the D-21..D-25 cockpit panels (LM orchestration, LM
status & operability, model catalog, CPU features, selfdef-management consumer
view) + the `profiles/orchestration/` intent-profile family.

## What got built (Phase 0 — SHIPPED, verified)

- **`scripts/operator/_action_exec.py`** — the shared execution primitive.
  Loads `config/control-systems.yaml`; **hard-rejects the 2 selfdef-owned
  controls** (selfdef, perimeter) at the R10212 boundary; validates every
  placeholder against the control's `options` allowlist / a strict
  no-shell-metacharacter regex; gates privileged controls on operator-key
  presence + explicit confirm; executes via `sudo -n` (mechanism isolated in
  `_privileged_argv` for B/C swap); single-flight lock; Prometheus counter
  `sovereign_os_operator_cockpit_action_total{control_id,outcome}`; OCSF-5001
  audit span into the **canonical M049 span log** (`SOVEREIGN_OS_SPAN_STORE`)
  that D-05/D-16 read. **DRY_RUN by default — import changes no host state.**
- **`config/sudoers.d/sovereign-os-cockpit`** — DRAFT/PREVIEW of the controls
  bucket (9 sovereign-os-owned verbs); visudo-clean.
- **`docs/sdd/047-cockpit-functional-execution.md`** — the spec (wired into the
  SDD INDEX + operator mandate E11.M14).
- Tests: `tests/unit/test_action_exec.py` (30) +
  `tests/lint/test_cockpit_action_exec_sudoers.py` (4 drift-guards).

Full local suite: **5094 passed / 39 skipped / 0 failed**.

## The mechanism, resolved from evidence

Investigation of the branch↔main divergence surfaced the real **"sudoer
strategy"**: **`scripts/operator/operator-sudoers.sh`** already exists on live
`main` (absent from this behind-branch). It generates
`/etc/sudoers.d/sovereign-os-operator` granting the **operator user** (that the
panel APIs + agent run as) a scoped NOPASSWD `Cmnd_Alias` (diagnostics + image
today; contract locked by `test_operator_sudoers.py` + `test_root_password_gate.py`).

- **Q-047-A answered**: extend `operator-sudoers.sh`'s generator with a controls
  bucket (the 9 owned `sovereign-osctl` verbs) — not a parallel file.
- **Q-047-C answered**: no dedicated user, no `NoNewPrivileges` drop — panels run
  as the operator user; `_action_exec` runs `sudo -n sovereign-osctl <verb>`.
- **Q-047-B open** (default: selfdef boundary stays a signed proxy).

## The branch-gate (Q-047-D — blocks Prod)

`claude/recover-projects-b0oT6` is an **unrelated history** vs a **fast-moving
`main`** (main advanced to `0c48a509` during this session). CI merges the
behind-branch against live main and fails on **main's own newer code the branch
lacks** — 8 identical `mkosi`/nspawn failures (my `mkosi-emit.sh` is the old
`Format=none`; main is the fixed `Format=ext4`). None from this arc's work.

A direct tree diff (`git diff origin/main HEAD`) shows **only 67 files differ**:
- **40 added** = this arc's clean deliverable (D-21..D-25 + `profiles/orchestration/`
  + `_action_exec.py` + SDD-047 + tests + systemd + docs) — re-applies cleanly.
- **~15 modified** = files where main is ahead (drift, e.g. the mkosi fix) —
  recreation absorbs main's correct version; only ~7 carry this arc's additions
  (dashboard-catalog / surface-map / nav-snippet / SDD INDEX / mandate / 2 tests).
- **12 main-only** = files this branch would *gain*, including `operator-sudoers.sh`.

**The unblock (one word from the operator): "recreate."** Rebuild the branch on
live `origin/main`, re-apply the 40-file deliverable (reconciling the ~7 additive
files onto main's versions + folding the controls bucket into
`operator-sudoers.sh`), and CI goes green + the PR (#23) becomes mergeable. A
local backup ref `recover-preserve` holds the current head. Recreation was NOT
done unilaterally — it rewrites history + the PR, and the operator's explicit
branch-restart authorization is conditioned on the PR being merged (it is not).

## Commits (this arc, on `claude/recover-projects-b0oT6`)

`c054e3ed` orchestration family · `9ddae5eb` D-25 panel · `9b50cb63` SHIPPED ·
`c720b05a` catalog CI-fix · `059f076c` Phase 0 primitive · `9dabf126` SDD-047 ·
`8aa9f8c5` observability metric · `ea895c4b` audit coherence · `4f9ec605`
Q-047-A/C evidence resolution · `6fddcbb7` sudoers operator-user correction.

## Way forward (post-recreate)

1. Fold the controls bucket into `operator-sudoers.sh` (replace the DRAFT file).
2. **Phase 1** — extend `webapp/_shared/control-surface.js` with an Execute
   button (+ type-to-confirm for privileged) — one change lights all 47 panels;
   selfdef/perimeter stay copy-only.
3. **Phase 2** — the ~175 per-panel action buttons (sovereign-os-owned only).
4. **Phase 3** — invert the ~48 read-only-asserting contracts; add alert rules
   for `cockpit_action_total` once execution is live (premature before then).
