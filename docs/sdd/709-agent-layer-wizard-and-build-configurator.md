# SDD-709 — wire the agent layer into the setup wizard + build configurator (IMPLEMENTATION)

> Status: draft (implementation — closes the wizard/configurator half of the agent-layer gap)
> Owner: operator-directed 2026-07-14 (verbatim): *"so how does it work. is it even all documented and
> how deep does the configuration goes? I like when we have a proper IaC and scripts and integrations and
> setup wizard and auto-installs and auto-configuration."* → *"continue"* (Round B).
> Addresses: **F-2026-118** (agent layer wired into IaC + CLI + docs but not into the operator-facing
> build-time configuration surfaces — the `sovereign-osctl init` wizard and the build-configurator webapp).
> Continues **F-2026-117** (SDD-708 closed the doc half; this closes the wizard/configurator half).
> Mandate module: **E11.M709**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

SDD-703..707 built the agent layer (swappable frontend, OpenClaw runtime, open-computer sandbox, backend
hotswap); SDD-708 documented it. But the *build-time* knobs still reached the operator only two ways: by
hand-editing the profile YAML, or by exporting `SOVEREIGN_OS_*` env vars on the build command. The two
surfaces the operator explicitly named — *"setup wizard ... auto-configuration"* — did not drive them:

- **`sovereign-osctl init`** presented **5 fixed decisions** (profile · substrate · secure-boot · encrypt ·
  whitelabel) and never asked about the desktop or the agent runtimes.
- **`webapp/build-configurator`** surfaced only **3 of the bake toggles** (dev-tools · selfdef · graceful);
  the frontend selector and the two agent-runtime bakes were absent from the page, its POST body, and the
  `build-configurator-api.py` env translation.

So a self-contained image with (say) the open-computer kiosk as its default face and OpenClaw baked in
required the operator to *know the env-var names* — the opposite of "auto-configuration".

## What this SDD delivers (the wizard/configurator wiring + self-enforcement)

1. **`scripts/build/adapters/mkosi-emit.sh`** — a tri-state env-override seam (`_env_bake`): the build-host
   env can force a bake **on** (`SOVEREIGN_OS_BAKE_OPENCLAW=1`), force it **off** (`=0`), or leave it
   **unset** to inherit the profile's declared bake. `SOVEREIGN_OS_FRONTEND` likewise overrides the
   profile's default frontend. This is the single knob the two surfaces below drive — the profile stays the
   source of truth; the wizard/configurator are overlays on it.
2. **`scripts/operator/build-configurator-api.py`** — the `/api/run` handler translates the POST body's
   `frontend` / `bake_openclaw` / `bake_open_computer` into those env vars (frontend validated against the
   canonical `FRONTEND_CHOICES` set; the two bakes are tri-state present→`1`/`0`). Applied to the real build
   only, alongside the existing dev/selfdef/graceful knobs.
3. **`webapp/build-configurator/index.html`** — the run console gains an **agent-layer row**: a frontend
   `<select>` (profile-default · gnome · dashboards-kiosk · open-computer-kiosk · none) + two bake
   checkboxes. They POST with the run, live-preview in the "Build command" pane, and regenerate on change —
   the same UX contract as the existing bake toggles.
4. **`sovereign-osctl init`** — a **6th decision, "AGENT LAYER"**: the operator picks the default frontend
   and whether to bake each runtime (installed-off). The choices land in the init state file
   (`frontend` / `bake_openclaw` / `bake_open_computer`) and fold into the recommended build command in
   NEXT STEPS. The key is **never** collected here (runtime-only, per SDD-707).
5. **`tests/lint/test_agent_layer_build_config_contract.py`** (11 cases) — pins the whole chain: the emit
   override seam (+ the embedded Python is extracted and compiled), the API translation + validation, the
   webapp controls + POST body + command preview, and the wizard decision + state fields (exercised by
   running the wizard non-interactively). `tests/nspawn/test_sovereign_osctl_init.sh` is updated to the
   6-decision reality.

## An honest finding — the §1g governance-tracker registration is *not* done here (and why)

SDD-708's Round B scope named a third follow-on: register frontend/openclaw/open-computer in
`surface-map.py` / `doc-coverage.py` "with a formally-registered `cli_only` waiver". Investigating the
actual structure *from the project* gave an honest answer that changes the recommendation:

- `surface-map.py`'s `MODULE_COVERAGE` is a curated **§1g cockpit-module** registry, and
  `test_surface_map_contract.py::test_gaps_verb_exits_nonzero_when_below` enforces that **every** entry sits
  at *structural ceiling* — every one of the 8 surfaces is either shipped or waived with a **"not
  applicable — …"** rationale (the R478 classifier treats only that prefix, `self-referential`, or
  `candidates are` as structural; everything else is a **FUTURE** roadmap gap that makes `gaps` fire).
- The agent-layer subsystems genuinely **could** grow api/mcp/webapp/dashboard surfaces later (a "manage the
  runtime" REST endpoint, an MCP tool, a status panel). Their unshipped surfaces are honestly **FUTURE**,
  not structural-NA.
- There is **no `cli_only` ceiling category** in this system — only structural-NA vs FUTURE. So registering
  them would force a choice: mark the future surfaces "not applicable" (a *false* structural claim that
  games the `gaps=0` invariant and corrupts R478's entire anti-minimization purpose), or mark them FUTURE
  (which breaks the `gaps=0` invariant and reddens CI).

Neither is correct. The agent layer is already operator-discoverable via its osctl verbs, `osctl --help`,
`ai-backend.md` / `ops/manage.md`, and its SDDs; that discoverability does not depend on the §1g cockpit
map. So `surface-map.py` / `doc-coverage.py` are **left untouched**, and the "register with a `cli_only`
waiver" idea is retired as mis-shaped rather than deferred — recorded on **F-2026-118**. If the operator
later wants a §1g slot for these, the honest path is a new *waiver category* in the classifier (a "CLI-only
by sovereignty boundary" ceiling, like the weaver §17 note), decided deliberately — not a forced entry.

## Explicit non-goals (unchanged from SDD-708's Round B framing)

- **Cross-profile** — the `provisioning:` block (and thus the agent layer) still lives only in
  `sain-01.yaml`; generalizing it to the other four profiles is separate.
- **Gateway TLS (Q-206-003) and serve-vs-gatewayd (Q-957-A)** — reserved operator decisions, not flash-blocking.

## Verification

- `tests/lint/test_agent_layer_build_config_contract.py` — 11 cases green.
- `tests/nspawn/test_sovereign_osctl_init.sh` updated to the 6-decision wizard (bash `-n` clean).
- Full `tests/` + all 5 profiles + ruff + `bash -n` green. No units/metrics/schema changed — one emit seam,
  one API translation, one webapp row, one wizard decision, one lint.
