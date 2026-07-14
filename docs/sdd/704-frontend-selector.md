# SDD-704 — swappable boot-frontend selector: GNOME ↔ dashboards-kiosk, live (IMPLEMENTATION)

> Status: draft (implementation — first big round of the SDD-703 frontend arc)
> Owner: operator-directed 2026-07-14 (*"be able to chose at any point to start in one or another
> or even disable both, is that possible?"* → *"address everything sequentially … big round, big
> iteration"*); agent-authored.
> Addresses: **F-2026-113** (frontend not selectable/hotswappable) — CLOSED here.
> Design parent: **SDD-703** (the arc's design + decision package).
> Mandate module: **E11.M704**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.
> Stage: **implement** — ships the selector for the frontends that already exist
> (gnome / dashboards-kiosk / none); OpenClaw (SDD-705) + open-computer (SDD-706) are the
> subsequent big rounds.

## What this delivers

The operator can now choose, at build time AND live, what the box presents on the display —
without a reflash. Four frontends on one selector:

| frontend | what it shows | how it's presented |
|---|---|---|
| `gnome` | the near-stock GNOME desktop + the "Sovereign Dashboards" launcher | gdm3 on `graphical.target` (today's behaviour — the default) |
| `dashboards-kiosk` | a fullscreen kiosk straight to the :8100 dashboards hub | `cage` + a browser via `sovereign-frontend-kiosk.service` |
| `open-computer-kiosk` | a fullscreen kiosk to the open-computer sandbox UI | same kiosk unit, URL pointed at the sandbox (service lands in SDD-706) |
| `none` | headless | `multi-user.target`; gdm + kiosk disabled |

## Provisional decision adoption (from SDD-703)

The operator gave the arc a green light (*"big round"*) but has not separately answered SDD-703's
six decision rows. This round adopts the SDD-703 **recommendations as provisional, fully
overridable defaults** — none is locked, each is a profile field or a live `set`:

- **D1 default frontend = `gnome`** — behaviour-preserving, least surprise. `profiles/*.yaml`
  `provisioning.frontend.default` overrides it; the operator can flip live any time.
- **D2/D3 (open-computer depth + GPU)** don't affect this round (SDD-706).
- The selector itself is the mechanism that makes every one of these reversible — so shipping on
  the recommended defaults costs nothing and unblocks the "choose at any point" ask now.

## The seams (as implemented)

1. **Profile + schema** — a new `provisioning.frontend` block:
   `default: gnome|dashboards-kiosk|open-computer-kiosk|none` + `install: [<stageable stacks>]`.
   `schemas/profile.schema.yaml` gains the block (`additionalProperties:false`, enum-constrained);
   `profiles/sain-01.yaml` sets `default: gnome`, `install: [gnome, dashboards-kiosk]` (both stacks
   staged so the live switch to the kiosk works out of the box).
2. **mkosi-emit** — parses `provisioning.frontend` and threads
   `SOVEREIGN_OS_FRONTEND` + `SOVEREIGN_OS_FRONTEND_INSTALL` into the image postinst env (the gap
   SDD-703 identified: `gnome|minimal|none` was env-only, unreachable from the profile).
3. **provision-bake §5b** — passes the two env vars into `install-gui-dashboards.sh`.
4. **install-gui-dashboards.sh** — restructured from a single `SOVEREIGN_OS_DESKTOP` case into
   *stage each frontend in `install:` → activate the `default`*. The kiosk stack install adds
   `cage seatd firefox-esr`, stages the (disabled) kiosk unit, writes the kiosk env; the
   default-activation step toggles gdm vs kiosk + sets the boot target. Back-compat: with
   `SOVEREIGN_OS_FRONTEND` unset it derives from the legacy `SOVEREIGN_OS_DESKTOP` (none→none, else
   gnome), so every pre-SDD-704 caller behaves exactly as before.
5. **The kiosk unit** — `systemd/system/sovereign-frontend-kiosk.service` runs
   `scripts/operator/frontend-kiosk.sh` (a `cage`-hosted fullscreen browser at `FRONTEND_KIOSK_URL`
   from `/etc/sovereign-os/frontend-kiosk.env`). seatd (not PAM) grants DRM/seat access, so
   `NoNewPrivileges=true` stays on. It carries every compatible R171 clause (`ProtectHome=tmpfs`
   for an ephemeral browser profile, `RestrictNamespaces=false` for the browser's content-process
   sandbox) plus a whole-service `# HARDENING-WAIVER:` for the two aspects a live graphical session
   can't meet (a writable home + user namespaces). `[Install] WantedBy=graphical.target`; enabled
   only when a kiosk frontend is selected.
6. **The runtime switch** — `scripts/operator/frontend.py`, delegated to by a new
   `sovereign-osctl frontend {status|list|set}` verb:
   - `set gnome` → disable the kiosk unit, (re-)enable gdm3, `graphical.target`.
   - `set dashboards-kiosk` → write the kiosk URL (:8100), disable gdm3, enable+start the kiosk,
     `graphical.target`.
   - `set open-computer-kiosk` → same, URL → the sandbox (hints if SDD-706's service is absent).
   - `set none` → disable both, `multi-user.target`.
   - `status` / `list` → what's staged / default / active (selfdef-style verdict line).
   `SOVEREIGN_OS_FRONTEND_DRYRUN=1` prints the systemctl plan instead of running it (so the tool
   rehearses on a CI box with no init and the contract lint can exercise the real code paths).

## Verification

- `tests/lint/test_frontend_selector_contract.py` — **14 cases** pinning the whole chain
  (schema → profile → mkosi-emit → installer → unit → cli) AND exercising behaviour in dry-run
  (`set` writes the kiosk env for both kiosk targets + honours `--url`; `list --json` is pure JSON;
  unknown values rejected).
- systemd fleet lints green with the new unit: unit-hardening (waiver), fleet-hardening (4
  universal clauses + `ProtectSystem=full`), hardening-posture (`ProtectHome`/`RestrictNamespaces`
  present + acceptable), per-unit coverage (reachable via `[Install]` + referenced in the
  installer; structurally valid), install-coverage (README fleet count 119→120 / 99→100 service).
- `bash -n` clean on the installer + launcher; profile validates (jsonschema); frontend.py runs
  (list/status/set) in dry-run.
- **NOT verified**: a real kiosk session on hardware (cage + seatd + a browser on a live seat) —
  no display/GPU/seat in CI; same static-contract bar as every other hardware-touching unit. The
  kiosk unit ships disabled by default (gnome is the default frontend), so nothing changes at boot
  for the shipping profile until the operator selects a kiosk.

## Non-goals (this round)

- OpenClaw (SDD-705) + open-computer sandbox service (SDD-706) — the service axis of SDD-703.
- Wiring a GPU into any kiosk/sandbox (SDD-703 D3 — later).
- Re-theming GNOME (intentionally near-stock).
- Persisting a kiosk browser profile (ephemeral by design — `ProtectHome=tmpfs`).

## Cross-references

- `docs/sdd/703-swappable-frontend-and-agent-runtimes.md` — the arc design + decision package.
- `scripts/install/install-gui-dashboards.sh` · `scripts/build/adapters/mkosi-emit.sh` ·
  `scripts/build/provision-bake.sh` — the extended seams.
- `systemd/system/sovereign-frontend-kiosk.service` · `scripts/operator/frontend-kiosk.sh` ·
  `scripts/operator/frontend.py` — the new components.
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-113 (closed here), F-2026-114/115 (scoped,
  open for SDD-706/705).
- `docs/sdd/702-inference-model-provisioning.md` — the local OpenAI endpoint the service-axis
  frontends (SDD-705/706) will consume.
