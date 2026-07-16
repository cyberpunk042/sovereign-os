# SDD-985 — cockpit functional-execution close-out: decision-package (F-2026-035)

> Status: complete — **DECISION-PACKAGE RATIFIED + BUILD INCREMENT LANDED (2026-07-15)**
> Owner: operator-directed 2026-07-13 ("scope F-2026-035"); agent-authored.
> Addresses: **F-2026-035** (HIGH) — "Handoff 007's cockpit-execution plan is stalled and blocked on one operator word."
> Mandate module: **E11.M985**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.
>
> **Operator ratifications recorded (2026-07-15):**
> - **D1** Q-047-D closed as obsolete.
> - **D2** Q-047-B ratified — selfdef/perimeter stay signed-proxy.
> - **D3** Phase-0.5 reversal ratified — DRAFT sudoers kept as lockstep source.
> - **D4** `cockpit_action_total` alert rules landed (the one remaining build increment).
> - **D5** F-2026-035 sequenced independently of MS003.
>
> **F-2026-035 formally retired.**

## Why this is a decision-package (and the surprise inside it)

F-2026-035 reads as "the single largest planned UX unlock, stalled." Read-only
research (this session, across handoff-007, SDD-047, `control-surface.js`,
`_action_exec.py`, the sudoers, the contract tests) found the opposite:

> **The plan is substantially already shipped on disk.** The handoff document
> (frozen 2026-07-08) says "Phase 0 done; Phases 1–3 gated," but the working tree
> shows **Phase 0.5 folded, Phase 1 fully implemented, Phase 2 executed for the
> SDD-048..052 engines, and most of Phase 3 done by design.** The "stall" was a
> *documentation* stall, not an engineering one.

So the deliverable is **reconciliation + a handful of operator ratifications + one
small remaining increment** — not a green-field build. The finding's own hint
("re-validate the blocker (likely obsolete)") was right.

## What's actually shipped (verified in the tree)

| Phase | Plan said | Reality on `main` |
|---|---|---|
| **0** | shipped | ✅ `_action_exec.py` (R10212 boundary, placeholder validation, presence+confirm gate, `sudo -n`, single-flight lock, OCSF-5001 span, DRY_RUN default) + SDD-047 + tests |
| **0.5** | "replace/retire the DRAFT sudoers file" | ✅ folded — **but by a design *reversal***: `operator-sudoers.sh` `cockpit_alias()` reads `config/sudoers.d/sovereign-os-cockpit` **verbatim as the lockstep source** (kept in sync by `test_cockpit_action_exec_sudoers.py`). The DRAFT was **kept, not retired.** |
| **1** | Execute button in `control-surface.js` — "lights all 47 panels" | ✅ **done** — `cs-exec` Execute button for non-proxy controls (`:215`), full `execAction` POST to `/api/control/execute` with 200/403/409/400/404/405 handling, inline type-to-confirm (`askConfirm`), graceful degrade to Copy on 405/unreachable; `PROXY_ONLY=["selfdef","perimeter"]` hardcoded |
| **2** | ~175 per-panel action buttons (owned only) | ✅ executed for the SDD-048..052 engines (approvals / models / rollback / adapters / memory / sessions) — the sudoers bucket grew from 9 to ~45 verbs to match |
| **3** | invert ~48 read-only contracts + `cockpit_action_total` alerts | ◑ **partial by design** — the ONE write path (`control-exec-api.py`) has its contract inverted; the **26 per-panel daemons keep 405 read-only ON PURPOSE** (they are boundary daemons; the exec daemon is the sole write front). The **only genuinely-unshipped item is the `cockpit_action_total` alert rules** (0 found) — correctly deferred until execution was live. |

**Panel count note:** the plan says 47; the tree + `context.md` say **55** (8 engine
panels added since 2026-07-08). The 47 is stale; 55 is authoritative. Non-blocking.

## The MS003 linkage (sequencing — NOT a blocker)

The Execute rail is **independent of the MS003 signature decision (F-2026-034 /
SDD-984)**. It ships today on **presence + confirm + sudoers-allowlist + DRY_RUN**,
not a real signature: `_action_exec.py` checks operator-key *presence* only
(material never read), requires `confirm`, and writes a *label* `"status":
"r10274-signed-execute"` — no signature is minted or verified. So:

- **F-2026-035 delivers operator value NOW** behind the presence+confirm gate.
- **F-2026-034 (MS003) is a parallel hardening upgrade** that later slots a real
  signature into the *same* gate without re-architecting the Execute rail.
- They are **independent but adjacent.** F-2026-035 need not wait for MS003.

## The decisions (operator)

None of these is a build blocker; each is a *ratification of shipped reality* or a
small sequencing choice:

| # | Decision | Recommendation | Why |
|---|---|---|---|
| **D1** | **Close Q-047-D** (the "recreate the branch" gate) | **Close as obsolete** | Verified: `claude/recover-projects-b0oT6` merged to `main` via PRs #110–#118 (SDD-144..149 on main; no live branch ref). The gate is answered-by-events. |
| **D2** | **Ratify Q-047-B** — selfdef/perimeter stay a signed proxy (never executed locally) | **Ratify (bless the default)** | Already enforced in code (`_action_exec.py:53,260-270` → 409; `control-surface.js:36` `PROXY_ONLY`; `test_control_surface_execute_boundary.py`). Just needs your recorded yes. Preserves R10212 producer/consumer. |
| **D3** | **Ratify the Phase-0.5 reversal** — keep the DRAFT `sudoers.d/sovereign-os-cockpit` as the lockstep source `operator-sudoers.sh` reads, instead of retiring it | **Ratify** | The shipped design (single source, generator reads it verbatim, drift-linted) is cleaner than a hand-maintained parallel file — but it contradicts the written plan, so it deserves an explicit blessing. |
| **D4** | **Phase-3 alert rules** — add `cockpit_action_total` alert rules now, or keep deferred | **Add now (small increment)** | Execution is live-capable, so the "premature before execution" reason no longer holds. This is the one remaining implementation item — ~1 rules file, additive. |
| **D5** | **Sequencing vs MS003** | **Ship/close F-2026-035 independently** | Per the linkage above — no hard dependency. |

## Recommendation (one paragraph)

**Close Q-047-D as obsolete, ratify Q-047-B and the Phase-0.5 reversal (both bless
already-shipped, already-linted reality), and land the one remaining increment —
the `cockpit_action_total` alert rules — as a small follow-up SDD.** That formally
retires F-2026-035: the "biggest planned unlock" turns out to be **delivered**,
needing only sign-off + one alert-rules file. MS003 (SDD-984) proceeds on its own
track.

## Scope of the one remaining build (for the follow-up, not this package)

The `cockpit_action_total` alert rules: alert on the existing Prometheus counter
`sovereign_os_operator_cockpit_action_total{control_id,outcome}` (e.g. spikes in
`outcome="denied"` / `"error"`), in the observability rules surface. Small,
additive, observability-lane — coordinate via the SDD-981 board before editing if
another session owns that surface.

## Non-goals (of this package)

- Building anything (the plan is shipped; the one residual is scoped for a
  follow-up).
- Touching `_action_exec.py` / `control-surface.js` / the sudoers / the contracts —
  read-only research only; collision-safe.
- Closing F-2026-035 unilaterally — it **de-escalates from "stalled HIGH" to
  "shipped; close-out pending D1–D4"**, and closes when the operator ratifies +
  the alert rules land.

## Safety invariants

Docs only (this SDD + registries + the F-2026-035 ledger back-annotation). No
gatewayd/cockpit/`unsafe`/crate edits; every cited surface read, never written.
R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-035 (this package addresses it)
- `docs/handoff/007-cockpit-functional-execution-arc.md` — the plan · `docs/sdd/047-cockpit-functional-execution.md` — the spec + Q-047-A..D
- `webapp/_shared/control-surface.js` — the Execute button (Phase 1, shipped) · `scripts/operator/_action_exec.py` — the execution primitive (Phase 0)
- `config/sudoers.d/sovereign-os-cockpit` + `scripts/operator/operator-sudoers.sh` — the sudoers lockstep (Phase 0.5)
- `docs/sdd/984-ms003-commit-authority-decision-package.md` — the adjacent (independent) MS003 decision
