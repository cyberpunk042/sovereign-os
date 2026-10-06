# SDD-303 — Warp management: make the cockpit tell the truth, then give it real controls

> Status: shipped (2026-10-06)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-10-06
> Closes findings: E11.M303 (science-tools band, SDD-100) — operator directive 2026-10-06 ("Lets improve sovereign-os cockpit Science Tools and Warp Management" → scope answered: *reality loop + real controls + gallery*)
> Derived from: SDD-300 (the Warp panel + exec-rail wiring; its **Q-300-D** — vendor the shaders project so the host can render — is answered here), SDD-045/047 (control-exec rail), SDD-301/302 (the science instrument — audited, not re-litigated). SB-077 doctrine: a panel must never report a stale pretend as reality.

## Mission

SDD-300 shipped the Warp management panel when the ground truth was "the shaders
project is not resident on the host", so every surface honestly degraded to the
no-op banner. **The ground truth changed and the panel did not.** On this host
(verified 2026-10-06):

- the checkout **is resident** (`~/warp-solar-system-shaders`, a git repo),
- `warp-lang 1.15.0` **is installed**,
- three GPUs are live (RTX PRO 6000 Blackwell / RTX 5090 / RTX 4090),
- a real `warp render atom` completes in **4.0 s on the 4090**,
- eight saved renders sit on disk —

yet the read-side daemon still reported `checkout_resident: false, latest_render:
null`. The honest-degradation doctrine had silently become a **stale pretend**.
SDD-303 closes the lie, then deepens the management: real runner controls and a
saved-render gallery.

## Problem (verified, not assumed)

1. **Sandbox split-brain.** `sovereign-warp-api` runs as root with
   `ProtectHome=true`; `sovereign-control-exec-api` runs as `User=jfortin`.
   `warp_manage.render_store()` was `Path.home()/...` and the checkout default
   roots included `~/warp-solar-system-shaders` — invisible to the root daemon.
   The two daemons resolved *different* HOMEs, so the panel could never see the
   checkout or the renders the exec-rail produced.
2. **Catalog drift.** `config/warp-catalog.yaml` was pinned at 217 scenes / 20
   libs; the resident checkout had grown to **281 scenes / 21 libs** (plus new
   `simulate`/`reel` runners). Nothing told the operator the committed catalog
   lagged the engine.
3. **Thin management.** `render.py` supports `--device {auto,cpu,cuda}`,
   `--quality {auto,low,medium,high,ultra}`, `--look
   {clean,cinematic,film,dreamy,crisp}`, `--time`, `--frames`, `--gif`,
   `--video` — the cockpit exposed only bare `render <scene>`. Saved renders
   appeared nowhere except a single "latest" preview.

## The four moves

### 1 — Reality loop (machine-resident truth)

- **Canonical checkout** at `/opt/warp-solar-system-shaders` — already the first
  candidate in `warp_manage._DEFAULT_ROOTS`, ProtectHome-visible to *both*
  daemons. `warp sync` (new verb + `warp-sync` privileged control + sudoers line)
  clones or `--ff-only` pulls it; refuses anything but an https-GitHub source
  from the catalog and refuses a non-git occupied directory. **Q-300-D answered:
  vendor-by-checkout, not a submodule.**
- **Shared render store** — `render_store()` now resolves
  `SOVEREIGN_WARP_RENDER_STORE` → `/var/lib/sovereign-os/warp-renders` (when
  present) → per-user fallback. A fixed, HOME-independent machine path ends the
  split-brain: the root daemon reads exactly what the user-level rail writes.
- **Freshness marker** — `gen_catalog.py` records `source_git_rev` (schema:
  optional 40-hex); `warp status` compares it against the resident checkout's
  HEAD and reports `catalog_freshness: fresh | stale | unknown` (never a guess
  when either side is unresolvable). The committed catalog is regenerated:
  **281 scenes / 21 libs / 4 runners**.

### 2 — Real controls (the runner's power, gated and whitelisted)

- `warp-render` control `change_cli` grows to
  `sovereign-osctl warp render <scene> --device <device> --quality <quality> --look <look> --time <time>`
  — all free placeholders stay `_SAFE_VALUE`-clean at the rail, and `warp_manage`
  **whitelists every value again** (defense in depth; a recognized flag with a
  bad value is a hard error, never passthrough smuggling). Unrecognized extras
  keep the legacy `-- ARGS` passthrough semantics for the direct CLI.
- The panel gains a **render-options bar** (device/quality/look selects + time
  input) that every per-scene Render click carries; the chosen opts are recorded
  in the render metadata so the gallery captions what produced each frame.

### 3 — Gallery (renders come back)

- `warp renders [--limit N]` CLI + `GET /warp/renders` (warp-api, read-only)
  metadata list; `GET /api/control/warp-renders` and
  `GET /api/control/warp-render-image?id=<32-hex>` on the exec-rail daemon (the
  origin that already serves the latest-render preview, and already owns the
  render store as the cockpit service user). `render_image()` accepts only the
  32-hex id, refuses symlinks/non-PNGs/>16 MB, never a path.
- The panel gains a **Render gallery** strip (newest first, click-through to the
  full PNG), per-scene `▣ N rendered` chips in the scene table, and a live
  refresh after every applied render (no page reload).

### 4 — Truth strip

The status strip now shows scenes / libs / checkout / warp-lang **plus a
catalog-vs-checkout HEAD freshness badge** (green fresh / amber STALE with the
exact regenerate command / dim unknown) and the saved-renders count; when the
checkout is absent it surfaces the `sovereign-osctl warp sync` command instead of
a bare "absent".

## Wiring

- `config/control-systems.yaml`: `warp-render` extended, `warp-sync` added
  (`privileged: true` — writes under /opt; operator key + type-to-confirm).
- `config/sudoers.d/sovereign-os-cockpit`: `sovereign-osctl warp sync` added
  (lockstep test extended via the registry EXPECTED_IDS list).
- Registry lint `EXPECTED_IDS`: `warp-sync`.
- Panel API routes: the new endpoints live under the existing `/api/control`
  prefix — `gen-panel-routes.py --check` stays green.
- `config/dashboard-catalog.yaml`: warp entry re-described (counts live in the
  panel, not frozen in the catalog row), `refs: [SDD-300, SDD-303]`.

## Host activation (this box)

1. `git clone ~/warp-solar-system-shaders /opt/warp-solar-system-shaders` (origin
   pointed at the GitHub remote).
2. `install -d -m 2775 -o jfortin -g jfortin /var/lib/sovereign-os/warp-renders`
   + copy the eight pre-existing renders from the per-user store.
3. Install the updated cockpit sudoers.
4. Restart `sovereign-warp-api` + `sovereign-control-exec-api` (deployed paths are
   symlinks into the repo — restart is the deploy).

## Verification

- `tests/unit/test_warp_sdd303.py` (new): store resolution order, opts
  whitelist + hard-error semantics, legacy passthrough intact, gallery readers'
  path discipline (bad id / symlink / no-PNG), freshness tri-state, sync
  guardrails.
- `tests/unit/test_action_exec.py`: warp-render argv now carries the four
  controls; bad option → 400; `warp-sync` is privileged.
- `tests/schema/test_warp_catalog_schema_conformance.py`: extended for the
  optional `source_git_rev`.
- Live on this host: `warp status` through `:8138` reports `checkout_resident:
  true`, `catalog_freshness: fresh`, the real render count; the gallery serves the
  migrated PNGs.

## Out of scope (Stage N — proposed, not minimized)

| Q | question | status |
|---|---|---|
| Q-303-A | tui / mcp rungs for the warp module (mirrors SDD-301 Q-301-B for science): `sovereign-osctl warp renders`, `sync` already carry the §1g CLI rung; an MCP tool set would wrap warp-api read routes. | proposed |
| Q-303-B | `--frames/--gif/--video` controls (animated outputs) — needs output-size policy + store eviction posture before offering them from the rail. | proposed |
| Q-303-C | Render-store retention/pruning policy (age/size cap) once the gallery grows — mirrors SDD-301 Q-301-C. | proposed |
| Q-303-D | Per-scene hero thumbnails generated at catalog time (a gallery cell for every scene, not only rendered ones) — CI has no GPU, so generation must be operator-gated. | proposed |
| Q-303-E | The real DNA/protein science runners (SDD-301 Q-301-A / SDD-302 Q-302-A) — audited this round (SDD-302 landed download+verify); the next science move. | proposed |
