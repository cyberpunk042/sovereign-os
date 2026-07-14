# SDD-999 — build-pipeline safety: a missing/critical step must fail the build, not silently pass (F-2026-105..106)

> Status: draft
> Owner: operator-directed 2026-07-14 (build-and-flash readiness review, *"we need to fix everything before I build and flash … the IaC is ready through and through and will be done properly and in proper timing and sequence?"*); agent-authored.
> Closes: **F-2026-105** (HIGH), **F-2026-106** (HIGH).
> Mandate module: **E11.M999**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The directive

Second batch of the operator's build-and-flash fix-everything pass (after SDD-998's
first-boot ordering). Two build-pipeline scripts could emit a broken image while reporting
success — the antithesis of *"the IaC … will be done properly and in proper timing and
sequence."*

## F-2026-105 (HIGH) — the orchestrator silently skips a missing step, then reports "complete"

`scripts/build/orchestrate.sh` had an **inconsistent contract between dry-run and run**:

- `cmd_preflight` (dry-run) treats a missing/non-executable step script as a failure —
  `return 1` after counting it.
- `cmd_run` (the real build) hit the same condition and **`log_warn … "skipping (will land
  in subsequent PR)"` + `continue`**, then fell through to `log_info "build pipeline
  complete"` with success metrics.

So a `run` whose `08-image-sign.sh` or `09-image-verify.sh` (or any step) went missing —
deleted, un-executable, or an incomplete checkout — would **skip that build stage and still
report success**, emitting an unsigned or unverified image with no error. The "will land in
subsequent PR" wording is a development-era leftover; all nine step scripts now exist.

**Fix**: in `cmd_run`, a missing/non-executable step is now **fatal** — it logs the missing
step, refuses to emit an incomplete image, emits the `fail` pipeline metrics, and `exit 1`,
matching the dry-run contract. A deliberate partial pipeline during development is still
possible via `SOVEREIGN_OS_ALLOW_MISSING_STEPS=1` (records the gap as a failed step + keeps
the old skip). The default now can't silently drop a build stage.

## F-2026-106 (HIGH) — provision-bake treats EVERY step as non-fatal, including image-bricking ones

`scripts/build/provision-bake.sh` runs `set -uo pipefail` (no `-e`) and ends every step in
`|| log …` — **NON-FATAL BY DESIGN**, and correctly so for the many optional steps
(dashboards, GUI, live-reload, gatewayd, ghostproxy, UPS, node-exporter, config defaults):
a hiccup there must never brick the image build, and each degrades + is recoverable
post-flash. But the blanket `exit 0` at the end meant **even the load-bearing steps** were
non-fatal: if the operator account couldn't be created, or `systemctl enable
sovereign-firstboot.target` failed, provision-bake logged it "(non-fatal)" and the build
**still succeeded** — emitting an image with no operator login, or one whose first boot runs
no hardware setup (the very inertness SDD-998 fixed at the unit level, re-introduced if the
*enable* silently fails).

**Fix** (surgical, not a blanket `set -e` which would wrongly make every optional hiccup
fatal): a `crit` helper records a failure and increments `_CRIT_FAILURES`; the two
image-bricking steps call it, and the final `exit` is `1` when any critical failure occurred:

- **operator account** (§1): after the useradd block, verify `id "${OPERATOR}"` succeeds —
  a genuine absence is `crit` (no operator login is a broken deliverable).
- **first-boot target enable** (§6): on enable failure → `crit`; on success, **verify** the
  `multi-user.target.wants/sovereign-firstboot.target` symlink actually exists (an offline
  `systemctl enable` can no-op silently) — a missing symlink is `crit` (first boot would run
  no hardware setup).

Everything else stays non-fatal. A critical failure now fails the mkosi postinst loudly with
a summary, so the operator fixes it and re-bakes rather than flashing a broken image.

## Verification (real, observed)

- `bash -n scripts/build/orchestrate.sh scripts/build/provision-bake.sh` — both parse clean.
- `python3 -m pytest tests/lint/test_build_pipeline_verbatim.py
  tests/lint/test_shell_safety_flags.py tests/lint/test_graceful_shutdown_contract.py` →
  **32 passed** (the verbatim build-pipeline contract + shell-safety flags + graceful-shutdown
  contract all green with the edits).
- Full `tests/lint` green (see PR).

## Scope / safety

`scripts/build/orchestrate.sh` (`cmd_run` missing-step branch → fatal + override) +
`scripts/build/provision-bake.sh` (`crit` tracker + operator-account verify + first-boot
enable verify + conditional exit) + this SDD + registries. No Rust crate, no
gatewayd/cockpit/webapp change; no new dependency. All nine step scripts already exist and the
normal bake creates the operator + enables the target cleanly, so the stricter defaults do not
break the current build (the VM/emulator path leaves `BAKE_FIRSTBOOT` unset, skipping §6
entirely). Collision-safe. MS003 `unsigned-pending-MS003`.

## Non-goals

- Making the *optional* provisioning steps fatal (they are non-fatal by design — dashboards,
  GUI, gatewayd, ghostproxy, UPS, node-exporter all degrade gracefully and recover post-flash).
- A DKMS-build-failure surfacing pass inside the driver hook (Batch 3 — the GPU bring-up SDD).
- Re-architecting the step/state/resume model (unchanged; only the missing-step contract moves).

## Cross-references

- `scripts/build/orchestrate.sh` — `cmd_run` fatal-on-missing-step (matches `cmd_preflight`)
- `scripts/build/provision-bake.sh` — `crit` tracker + verify-enable + conditional exit
- `docs/sdd/998-firstboot-orchestration-correctness.md` — the first-boot unit-level fix this guards at the enable/build layer
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-105, F-2026-106 (closed here)
