# SDD-964 — systemd install coverage: `make install-units` + two-prefix doctrine + coverage contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-051** (objective/file-side core — `make install` installs no units; README over-claims). Prefix *unification* scoped as operator decision **Q-964-A**.
> Mandate module: **E11.M964** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The 111 systemd units (91 `.service` / 19 `.timer` / 1 `.target`) are the boot-time fleet, but **nothing installed them or the scripts they call**, and the unit README documented only 4 of the 111.

- `make install` staged the shared libs + `sovereign-osctl` under `$(PREFIX)/lib/sovereign-os/` — never `scripts/operator/`, never the `/opt` tree, and **zero `.service`/`.timer` files**. An operator following `systemd/system/README.md` (which described only the 4 inference units) got a fleet whose `ExecStart` paths didn't exist.
- The units reference **two script roots** by ownership — 54 operator-API units at `/usr/local/lib/sovereign-os/scripts/operator`, ~34 hook/inference/hardware units at `/opt/sovereign-os/scripts/…` — a real doctrine that was **undocumented and unenforced**, so it read as accidental drift.

Investigation confirmed the finding's key fact: all 88 script paths referenced across the fleet's `ExecStart*` lines **exist in-repo** (0 missing) — this is install-wiring + doc drift, not missing code.

## What this SDD builds

### 1. `make install-units` (+ `make uninstall-units`) — the file-side fleet install

Installs, **DESTDIR-clean** (stageable/packageable, no live-system touch required):

- every `systemd/system/*.{service,timer,target}` → `/etc/systemd/system/`, and
- the three script trees the units reference, at the exact roots their `ExecStart` lines hardcode:
  - `scripts/operator/` → `/usr/local/lib/sovereign-os/scripts/operator`
  - `scripts/{hooks,inference,hardware}/` → `/opt/sovereign-os/scripts/…`

It prints the activation step (`systemctl daemon-reload` + selective `enable --now`) rather than running it — file staging is verifiable; unit *activation* needs a real systemd + root and stays the operator's runtime step. `make install` now points at `install-units` for the fleet; `uninstall-units` reverses it.

### 2. `systemd/system/README.md` — the full fleet + two-prefix doctrine

Extended (additively — the inference-tier section is preserved) with: the 111-unit fleet size, the `make install-units` flow, and the **two-prefix doctrine** table (operator-API → `/usr/local/lib` FHS; hook/inference/hardware → the `/opt` vendor tree) with the rationale for each root.

### 3. `tests/lint/test_systemd_install_coverage.py` — the coverage contract

Fails CI if: any unit's `ExecStart` script doesn't resolve to a real in-repo file; a unit references a script root outside the two documented prefixes; `make install-units` stops staging one of the three trees or the units; or the README's stated fleet counts drift from the tree. So `make install-units` **provably stages a working fleet** (every referenced script is real), and the doctrine can't silently rot. Same self-maintaining discipline as the island register (SDD-955) and route-parity (SDD-956).

## Q-964-A — prefix unification (operator decision, deferred)

Should the two-root split be **unified** onto a single install root, or kept as the deliberate ownership doctrine it now is?

- **Recommendation: keep the split.** It is coherent once documented + contracted — `/opt` is the image-build vendor tree for boot hooks/inference/hardware; `/usr/local/lib` is the FHS home of the operator control-plane installed with `PREFIX`. Unifying would rewrite 54+ units' `ExecStart` paths — a large mechanical change that must be smoke-tested on a real booted box (systemd activation), which this sandbox can't do.
- **If the operator wants a single root** (e.g. for a distro package with one `%files` tree), it becomes a deliberate follow-up sweep: pick the root, rewrite every `ExecStart`, re-point `install-units`, and validate on hardware. The coverage lint already guarantees the sweep would be complete (no unit left pointing at the old prefix).

## Verification

- `make install-units DESTDIR=/tmp/su-stage` → 111 unit files staged to `/etc/systemd/system`; all 88 `ExecStart` script paths resolve **in the staged tree** (0 missing) — a complete, runnable file-side fleet.
- `python3 -m pytest tests/lint/test_systemd_install_coverage.py` — 4 passed (every script in-repo; prefixes documented; install-units stages the 3 trees + units; README counts match tree).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Unifying the two prefixes** — Q-964-A, operator decision (touches 54+ units, needs on-hardware validation).
- **`systemctl enable`/activation** — file staging is in scope; unit activation is the operator's root runtime step (correctly deferred, printed by the target).
- **Per-unit hardening/ordering audit** (F-2026-054 per-unit test coverage) — a sibling finding.
- **Env-file provisioning** beyond the existing inference-tier `.env` flow.

## Safety invariants

Build-tooling + docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. `make install-units` is DESTDIR-stageable and does not enable or start any unit; it stages files the repo already ships to the paths the units already reference (invents nothing). R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `Makefile` — `install-units` / `uninstall-units` targets
- `systemd/system/README.md` — the full fleet + two-prefix doctrine
- `tests/lint/test_systemd_install_coverage.py` — the coverage contract
- `scripts/install/install-sovereign-root.sh` — the root installer (gatewayd + power-guard units)
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-051 (source); F-2026-054 (per-unit test coverage sibling)
- SDD-955 / SDD-956 / SDD-963 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
