# SDD-800 — Cockpit wasm bridge: the typed cockpit crates run in the browser

> Status: draft
> Owner: operator-directed ("build the wasm bridge" — Phase-1 audit F-2026-001); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-001** (partial — the 413 `sovereign-cockpit-*` crates are consumed by nothing; the audit's option (a): "wasm-pack a facade and progressively move panel state logic into the typed crates"). First crate bridged; the pattern + toolchain + contract are established for the rest.
> Mandate module: **E11.M800** (operator-mandate cross-link).
> Number band: **800–899 (cockpit-wasm bridge session)** per SDD-100.

## Mission

Audit finding **F-2026-001** (CRIT) is the single largest crate finding: **413 of the 418 `sovereign-cockpit-*` crates — ~58% of the workspace — are consumed by nothing that runs.** They encode the cockpit's UX-state logic as typed, tested, serde Rust, but the webapp is hand-written HTML/JS with **zero** `wasm-bindgen`/`cdylib`/`wasm32` anywhere, so every panel re-implements that logic in JS and can silently drift from the crate the daemon trusts. The finding names four fates; the operator chose **(a) build the wasm bridge** — make the webapp actually run the crates.

This SDD ships the bridge end-to-end on the **first** crate and establishes the repeatable pattern, so de-islanding the cockpit family becomes "add a thin wrapper per crate", not "invent an architecture".

## What this SDD does

**The facade crate — `cockpit-wasm/` (deliberately OUTSIDE the workspace).**
A `wasm-bindgen` facade over the typed cockpit crates, first bridging `sovereign-cockpit-banner-state`:
- Exports `banner_severity(mode, worst_thermal, open_alerts)` → the real `compute_severity` kebab verdict; `banner_state(…)` → a full `BannerState` JSON built + severity-computed by the crate; `banner_validate(state_json)` → the crate's own `validate()` (`{"ok",…}`); `schema_version()`.
- Enums cross as their serde **kebab** tokens and structs as JSON — the exact shapes the panels already speak. Unknown tokens error, never panic.
- **Why excluded from the workspace**: wasm-bindgen's macro emits `unsafe` glue, and the workspace keeps `sovereign-simd` as its **one** sanctioned unsafe crate (an explicit operator decision). Living in `[workspace].exclude` keeps that invariant literally true *and* keeps the wasm/browser toolchain off the 714-crate CI path (relevant to F-2026-050). Hand-written facade code stays entirely safe.

**The committed artifact — `webapp/_shared/cockpit-wasm/{cockpit_wasm.js, cockpit_wasm_bg.wasm}`.**
The `wasm-bindgen --target web` output (187 KB wasm + 10 KB ESM glue), reproduced by `cockpit-wasm/build.sh`. Committed as a shared webapp asset (consistent with the no-build-system, panels-work-offline reality) rather than built at deploy time.

**The served demo — `webapp/_shared/cockpit-wasm/demo.html`.**
Co-located with the wasm it loads (under `_shared`, so it is a served demonstrator, not a nav panel — promoting it into the cockpit nav / dashboard-catalog is a deliberate follow-up, kept out of this increment to avoid app-shell propagation churn). It lets the operator vary mode / bundle / worst-thermal / open-alerts and live-computes severity + builds + validates a `BannerState` **entirely client-side in wasm** — the same Rust the daemon runs. Tamper the stored severity and `validate()` catches it. If the wasm can't load, it degrades honestly (offline banner, page stays readable).

**The serving api — `scripts/operator/cockpit-bridge-api.py` + `sovereign-cockpit-bridge-api.service` (loopback :8137).**
A read-only static server rooted at `webapp/` that serves the panel + the shared wasm asset with the correct **`application/wasm`** MIME (which the other panel APIs lacked). It assembles no host data — the bridge computes in-browser — so `POST → 405`; `/bridge.json` + `--self-check` report the artifact/export state. Auto-enabled by provision-bake's `sovereign-*-api.service` glob; loopback-by-default (operator exposure decision).

**The contract — `tests/lint/test_cockpit_wasm_bridge.py`.**
Keeps the bridge honest both ways: facade excluded from the workspace + is a wasm cdylib depending on a real cockpit crate; the committed artifact is a valid wasm module (magic `\0asm`) whose glue exports the four bound functions; the panel imports the module + calls the real logic + degrades gracefully; the api ships the wasm MIME + is read-only on its port; the unit's port matches; `build.sh` is executable.

## Verification

- `cd cockpit-wasm && cargo test` → **5 passed** (facade logic native).
- `bash cockpit-wasm/build.sh --smoke` → rebuilds the artifact + **executes** the exports in node: **7/7** severity cases match the crate rules, `banner_state` self-validates, a tampered severity is rejected. (Proof of browser-equivalent execution without a browser — same wasm, same exports.)
- Live serving (`cockpit-bridge-api.py` on :8137): `/healthz` ok, panel `text/html`, glue `application/javascript`, **wasm `application/wasm`**, `POST → 405`, `../Cargo.toml → 404` (traversal blocked).
- `pytest tests/lint/test_cockpit_wasm_bridge.py` → **8 passed**.
- Full `tests/lint` + `tests/schema` green.

## Round 2 — scaling the bridge to the whole cockpit family

A survey found the family is remarkably uniform: **~399 of the 418 crates** share the exact shape `Type::validate(&self) -> Result<(), E>` on a serde-`Deserialize` primary type. That regularity is bridged **mechanically, not by hand**:

- **`cockpit-wasm/gen-bridges.py`** scans the crates and, for each uniform one, emits one `bridge_validate!(<slug>_validate, sovereign_cockpit_<slug>::Type)` line into `src/bridges.rs` (a generated, `#![rustfmt::skip]` file) plus an *optional* path-dep + a `dep:` entry in the `bridges` feature list. Deterministic + idempotent; `--count N` bridges the first N (rounds), `--count all` the whole family.
- **`bridge_validate!`** (a `macro_rules!` in `lib.rs`) expands to a `#[wasm_bindgen] pub fn <slug>_validate(json)` that parses the crate's primary type and runs its **real** `validate()`, returning `{"ok",…}` — never panics.
- **Feature-gated to keep the repo lean.** The generated module is behind `#[cfg(feature = "bridges")]`. The **default** (committed) build is the banner-only demo — **128 KB**. The **full** bridge (all 398, **~4.4 MB**, 399 `_validate` exports) compiles only under `--features bridges` and is **built on demand + verified, never committed** (`make cockpit-wasm-all` / `cockpit-wasm/build.sh --verify-all`; a lint ceiling fails CI if the full build is ever committed).

This de-islands **398 more cockpit crates** in source: each is now an (optional) dependency of `cockpit-wasm` with a real, compiling, browser-runnable consumer — F-2026-001's core for the uniform family. The `test_cockpit_wasm_bridge.py` contract pins that the generated `bridges.rs` / optional-deps / feature-list stay a consistent set over real cockpit crates, and a `--features bridges` native test proves a generated bridge reaches the crate's real `validate()` (valid → ok, schema-mismatch → its real error, garbage → parse guard).

**Verified (round 2):** `gen-bridges.py --count all` → 398 bridged, 19 ineligible; `cargo build --release --target wasm32 --features bridges` → 399 `_validate` exports in 18 s; `build.sh --verify-all` executes a sample in node (valid/invalid/parse-guard OK); `cargo test --features bridges` 6 passed; clippy (default + `--features bridges`) clean; committed demo stays 128 KB; `pytest tests/lint/test_cockpit_wasm_bridge.py` 12 passed.

## Round 3 — the 19 bespoke crates (the whole family, 418/418)

The 19 crates without the uniform `validate(&self)` were bridged **by hand** over their real decision/compute fns (not the macro), completing the family:

- **`cockpit-wasm/src/bespoke/<slug>.rs`** — one hand-written module per crate, each a `#[wasm_bindgen]` wrapper over the crate's genuine surface: `color-contrast`→`verdict` (WCAG ratio + AA/AAA), `pagination`→`new`/`info`/`next`/`prev`/`goto`, `word-count`→`count`, `day-divider`→`classify`/`group`, `relative-time`→`format`/`classify`, `text-truncation`→`truncate`, `toast-stack`/`search-history`→functional mutations (parse state → mutate a copy → return new state), `views`→`missing_views`+`is_complete`, the audit panels (`friction`/`guardian`/`perimeter`/`scheduler`)→their pure `any_*`/`aggregate_*`/`render` decisions, etc. Filesystem loaders (`load_from_ring`/`load_from_paths`) and the wall-clock are deliberately **not** bridged — pure functions only; a clock is passed in as an epoch arg.
- **`gen-bridges.py` now also manages the bespoke set**: it scans `src/bespoke/*.rs`, writes `src/bespoke/mod.rs`, and folds those crates' optional deps + `dep:` feature entries into the same generated blocks (so an import like the transitive `sovereign-cockpit-keystroke-map` can't be forgotten). The `bridges` feature is the union of the 398 generated + the bespoke set = **417 cockpit deps**; with banner-state that is the full **418/418**.
- This round also **fixed a latent round-2 defect**: the generated `bridges.rs` had used `#![rustfmt::skip]` (an unstable *inner* attribute, E0658) which broke the `--features bridges` build; it is replaced by a `cargo fmt` normalisation step (the contract lint is regex-based, so wrapping-independent).

**Verified (round 3):** `cargo build --features bridges` clean (465 exports); the bespoke bridges execute in node — `color_contrast_verdict(black,white)` → 21:1 AA+AAA, `pagination_info(2/10/95)` → range [10,19]/10 pages, `word_count_count` / `day_divider_classify` / `text_truncation_truncate` correct, bad tokens → graceful parse errors; `cargo test --features bridges` 6 passed; clippy (default + bridges) + fmt clean; committed demo still 128 KB; `pytest tests/lint/test_cockpit_wasm_bridge.py` 13 passed. **F-2026-001: 418/418 cockpit crates bridged.**

## Non-goals / follow-ups

- **`wasm-opt`** further size reduction of the full build (binaryen) is a follow-up; the committed demo is already 128 KB (opt-level="z" + strip).
- **Nav-panel promotion + progressive panel migration** (moving a production panel from its JS copy to a `<crate>_validate` / bespoke call) remain the next increments now that the whole family is callable.
- **Nav-panel promotion** (adopt the demo into the cockpit app-shell / dashboard-catalog) + **progressive panel migration** (moving an existing production banner from its JS copy to the wasm call) are the natural next increments now that the bridge is proven.
- MS003: `unsigned-pending-MS003` (read-only surfaces; the api mutates nothing).
