# SDD-700 — operator sudoers: risk-tier the OPS grants + lock them against privilege-escalation drift (F-2026-107..108)

> Status: draft
> Owner: operator-directed 2026-07-14 (build-and-flash readiness review, *"everything that needs to be in the sudoer are there too?"*); agent-authored.
> Closes: **F-2026-107** (MED), **F-2026-108** (LOW).
> Mandate module: **E11.M700**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100. The phase-1 audit band 950–999 filled (SDD-998/999 took its last slots); this arc continues in the next free disjoint block per the SDD-100 rule.

## The directive

Part of the build-and-flash readiness pass. The operator asked directly:

> "everything that needs to be in the sudoer are there too?"

The right answer has two halves — *are the needed commands granted?* (yes: diagnostics +
image-verify + the cockpit control verbs) and, the one nothing was guarding, *are ONLY the
right things granted, and can't a dangerous one drift in?*

## F-2026-107 (MED) — the OPS sudoers bucket had no coverage lint and no privesc guard

`scripts/operator/operator-sudoers.sh` installs a scoped NOPASSWD drop-in for the operator
(the panels + the AI agent run as that user). It has two surfaces:

- **the cockpit control verbs** — a per-verb `SOVEREIGN_OS_COCKPIT` alias, kept in lockstep
  with the control registry and proven to never contain selfdef/perimeter verbs by
  `tests/lint/test_cockpit_action_exec_sudoers.py`. **Well-guarded.**
- **the OPS bucket** — one opaque `SOVEREIGN_OS_OPS` alias built from three shell arrays
  (`DIAG` read-only probes, `IMAGE` loop-mount, `PROC` kill). `test_operator_sudoers.py`
  checked it was *not* `NOPASSWD: ALL` and that entries were absolute paths — but **nothing
  kept its command set the reviewed one, and nothing forbade a privilege-escalating binary**
  (`dd`, `bash`, `systemctl`, `tee`, `chmod`, `python`, `find -exec`…) from being added.

A single edit adding `bash` (or `dd`, or `systemctl`) to the `DIAG` array would silently turn
the "scoped, reviewable" drop-in into **root-equivalent** — a NOPASSWD root shell — and every
lint would still pass. For a drop-in whose whole selling point is "deliberately an allow-list,
never `ALL`," that is the real hole behind the operator's question.

**Fix — two moves:**

1. **Risk-tier the aliases** so the `/etc/sudoers.d` file self-documents danger. The one
   `SOVEREIGN_OS_OPS` alias becomes three: `SOVEREIGN_OS_DIAG` (read-only diagnostics — low
   risk), `SOVEREIGN_OS_IMAGE` (**HIGH-RISK**: loop-mount an image to verify it), and
   `SOVEREIGN_OS_PROC` (process control). A reviewer now sees at a glance which grants are
   powerful; the grant line lists only scoped aliases, never a raw command.

   **Follow-up (2026-07-17):** `journalctl` was split out of `DIAG` into its own
   `SOVEREIGN_OS_JOURNAL` tier with a **forced `--no-pager` first argument**. A bare
   NOPASSWD `journalctl` is a GTFOBins pager→root escape — on a tty it auto-launches a
   pager (`less`), and `!sh` in `less` yields a root shell, invisible to the basename
   privesc-denylist (which blocks `less` as an *entry* but can't see journalctl's *internal*
   pager spawn). The `journalctl --no-pager *` grant never launches a pager, closing the
   escape while keeping passwordless log reads. This is the one sanctioned exception to the
   "no arg-scoping" non-goal below: forcing a *safe* flag is the opposite of the dangerous
   pattern (a wildcard that *widens* a grant).

2. **Lock + guard the command set** in `test_operator_sudoers.py`:
   - **lockstep**: each tier's command set must equal the reviewed set (`EXPECTED_DIAG` /
     `EXPECTED_IMAGE` / `EXPECTED_PROC`) — a new grant requires a deliberate, reviewed change
     to the lint (the same drift-lock the cockpit alias already has);
   - **privesc denylist**: no tier may contain any of a curated denylist of trivially
     root-escaping binaries (shells, interpreters, `dd`, `tee`, `chmod`, `chroot`,
     `systemctl`, package managers, pagers/editors with shell escapes, `find`/`tar`/`rsync`
     with command-exec flags, `su`/`sudo`/`passwd`…) — defense-in-depth even if both the
     script and `EXPECTED_*` were edited together.

The image loop-mount primitives (`losetup`/`mount`/`umount`) stay — they are the reviewed,
deliberately-HIGH-RISK grants image verification needs — but they now live in their own
clearly-labelled tier, not blended into an opaque bucket.

## F-2026-108 (LOW) — `_action_exec.py` docstring points at a non-existent sudoers path

`scripts/operator/_action_exec.py`'s "Sudoer strategy" docstring referenced
`systemd/sudoers.d/sovereign-os-cockpit`. That path does not exist — the reviewed draft lives
at `config/sudoers.d/sovereign-os-cockpit` (where `operator-sudoers.sh` and the cockpit lint
both read it). A wrong path in the one doc that explains the execution primitive's trust model
sends a reviewer to the wrong file. **Fix**: corrected to `config/sudoers.d/…`.

## Verification (real, observed)

- `bash -n scripts/operator/operator-sudoers.sh` clean; `operator-sudoers.sh --print`
  emits the three tiered aliases + the cockpit alias, and `visudo -cf` **parses OK**.
- `python3 -m pytest tests/lint/test_operator_sudoers.py
  tests/lint/test_cockpit_action_exec_sudoers.py` → **12 passed** (lockstep + privesc-denylist
  + tier-separation + the existing not-blanket-ALL / self-validating / make-target checks).
- `ruff` clean. Full `tests/lint` green (see PR).

## Scope / safety

`scripts/operator/operator-sudoers.sh` (tiered `build_body` + `_resolve_bucket` helper) +
`tests/lint/test_operator_sudoers.py` (lockstep + denylist + tier lints) +
`scripts/operator/_action_exec.py` (one docstring path) + SDD-700 + registries + the SDD-100 /
`docs/sdd/README.md` band row for 700–799. No Rust crate, no gatewayd/cockpit/webapp change; no
new dependency. The generated sudoers content is unchanged in *effect* (same commands granted;
only split across three named aliases), visudo-valid, and the install stays self-validating +
mode 0440. Collision-safe. MS003 `unsigned-pending-MS003`.

## Non-goals

- Argument-scoping the general-purpose OPS binaries via sudoers wildcards — `mount`/`zfs`/
  `kill`/`journalctl` are general tools where sudoers arg-wildcards are a known footgun (a
  badly-scoped wildcard is worse than a documented whole-binary grant); the reviewed lockstep +
  privesc denylist is the durable guard, and the per-verb arg-scoping model already exists
  where it is safe (the cockpit `sovereign-osctl <verb>` alias).
- Changing which commands are granted (the reviewed set is unchanged; this only guards it).
- The daemon `NoNewPrivileges=true` vs `sudo` interaction called out in `_action_exec.py`
  (a separate Phase-0-wiring decision).

## Cross-references

- `scripts/operator/operator-sudoers.sh` — risk-tiered `SOVEREIGN_OS_DIAG`/`_IMAGE`/`_PROC` aliases
- `tests/lint/test_operator_sudoers.py` — lockstep reviewed-set + privesc denylist guard
- `tests/lint/test_cockpit_action_exec_sudoers.py` — the sister lockstep lint for the cockpit verbs
- `scripts/operator/_action_exec.py` — the execution primitive whose docstring path is fixed
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-107, F-2026-108 (closed here)
