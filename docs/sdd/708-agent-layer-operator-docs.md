# SDD-708 — document the agent layer for the operator (+ a drift lint) (IMPLEMENTATION)

> Status: draft (implementation — closes the operator-doc half of the agent-layer gap)
> Owner: operator-directed 2026-07-14 (verbatim): *"so how does it work. is it even all documented and
> how deep does the configuration goes? I like when we have a proper IaC and scripts and integrations and
> setup wizard and auto-installs and auto-configuration."*
> Addresses: **F-2026-117** (agent layer wired into IaC + CLI but absent from operator-facing docs, the
> wizard/configurator, and the project's own governance trackers) — **doc half CLOSED here**; wizard/
> configurator + governance-tracker registration scoped as follow-ons.
> Mandate module: **E11.M708**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## What the double-check found

The operator asked how it works, how deep the config goes, and whether it's documented. Mapping the
surfaces *from the project* gave an honest answer: the agent layer (frontend selector SDD-704, OpenClaw
705, open-computer 706, backend hotswap 707) is **fully wired end-to-end** — profile → strict schema
(505 lines, ~202 fields) → `mkosi-emit` → `provision-bake` → first-boot hooks → systemd units →
`sovereign-osctl` verbs — and each link is pinned by a dedicated contract lint. **But those contracts stop
at the CLI `--help` text.** The agent layer had reached **no** operator-facing surface:

- **mdbook / operator docs** — `ai-backend.md`, `ops/manage.md`, `profiles/sain-01.md`, the man page: 0 mentions.
- **setup wizard + build configurator** — `sovereign-osctl init` (5 fixed decisions), `wizard/onboard.py`,
  and `webapp/build-configurator` (only 3 of 8 bake toggles, 12 fixed sections): 0 mentions of the new options.
- **the project's own §1g governance trackers** — `surface-map.py` / `doc-coverage.py` don't track
  frontend/openclaw/open-computer as modules, so the anti-minimization audit is blind to the gap, and the
  `cli_only` waiver named in the 705/706 SDD prose was never formally registered.

So the *auto-install + auto-config + scripts* are solid; the *docs + wizard + governance* lagged.

## What this SDD delivers (the doc half + self-enforcement)

1. **`docs/src/ai-backend.md`** — the cohesive operator guide gains a **"The desktop + the agent runtimes"**
   section: the `frontend set` face-swap, the OpenClaw + open-computer installed-off lifecycle, and the
   `backend {local|anthropic}` hotswap — with the build-time profile knobs and the **key-never-baked**
   discipline spelled out. (This is the natural home — the page is already "Use the box as your AI backend".)
2. **`docs/src/ops/manage.md`** — the lifecycle handbook gains a **"Desktop + agent runtimes"** verb section.
3. **`docs/src/profiles/sain-01.md`** — an "Agent layer" note (this is the one profile that bakes it).
4. **`tests/lint/test_agent_layer_docs_contract.py`** (6 cases) — a **drift guard**: every agent-layer verb
   the CLI dispatches (`frontend`/`openclaw`/`open-computer`) must appear in `ai-backend.md`; the guide must
   document the local↔anthropic swap + the never-baked key; `manage.md` must list the verbs; the guide must
   be reachable from SUMMARY. So the docs can't silently fall behind the CLI again.

## Explicit non-goals (scoped follow-ons — the operator's Round B)

- **The setup wizard / build configurator** — surfacing `frontend` (a select), `bake.openclaw` /
  `bake.open_computer` (checkboxes), and the backend/anthropic fields in `webapp/build-configurator`
  (a 4,625-line webapp) + `build-configurator-api.py` + `sovereign-osctl init`. That's a real, separate
  round (touches the webapp) — deliberately not bundled here.
- **Governance-tracker registration** — adding frontend/openclaw/open-computer to `surface-map.py` /
  `doc-coverage.py` (with a formally-registered `cli_only` waiver) so the project's own §1g audit tracks
  them. Interacts with the multi-surface coverage thresholds; done deliberately in the wizard round.
- **Cross-profile** — the `provisioning:` block (and thus the agent layer) currently lives only in
  `sain-01.yaml`; generalizing it to the other four profiles is separate.

## Verification

- `tests/lint/test_agent_layer_docs_contract.py` — 6 cases green.
- Full `tests/` + all 5 profiles + ruff green. No code/units/metrics changed — docs + one lint.

## Cross-references

- `docs/src/ai-backend.md` (extended) · `docs/src/ops/manage.md` (extended) · `docs/src/profiles/sain-01.md`.
- The agent layer: `docs/sdd/704-frontend-selector.md` · `705-openclaw-agent-runtime.md` ·
  `706-open-computer-sandbox.md` · `707-agent-runtime-backend-hotswap.md`.
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-117 (doc half closed here).
- Follow-on surfaces: `scripts/wizard/onboard.py` · `scripts/operator/build-configurator-api.py` ·
  `webapp/build-configurator/index.html` · `scripts/operator/{surface-map,doc-coverage}.py`.
