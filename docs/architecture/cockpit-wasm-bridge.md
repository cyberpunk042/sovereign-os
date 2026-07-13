# The cockpit-wasm bridge — how it's built and how it works

> Audience: **you do not need to know Rust or WebAssembly.** This is the plain-language
> guide to what the bridge is, why it exists, and how a browser panel ends up running
> real Rust logic. Every term is defined the first time it appears.
> Formal spec: [docs/sdd/800-cockpit-wasm-bridge.md](../sdd/800-cockpit-wasm-bridge.md). Audit finding: **F-2026-001**.
> Companion map: [docs/architecture/crate-inventory.md](./crate-inventory.md).

---

## 1. The one-paragraph version

The cockpit (the web dashboard) has **418 small Rust libraries** that encode its UI logic
— how to sort alerts by severity, when the top banner turns red, which tree rows are
visible, and so on. For a long time **nothing ran them**: the web pages were hand-written
HTML + JavaScript, so each page re-implemented that same logic in JS by hand, and the two
copies could quietly disagree. The **cockpit-wasm bridge** fixes that: it compiles the real
Rust logic into a form the browser can execute (**WebAssembly**), and a small shared script
lets any panel call the *real* Rust function instead of a hand-written JS copy. Same logic
the backend trusts, now running in the page.

---

## 2. Vocabulary (read once, refer back)

| Term | Plain meaning |
|---|---|
| **crate** | A Rust library — one folder of Rust code that does one job. `sovereign-cockpit-alert-group` is a crate that groups alerts by severity. There are 418 cockpit crates. |
| **WebAssembly / wasm** | A compiled format browsers can run at near-native speed. Think of it as "a program the browser can execute" that was written in something other than JavaScript (here: Rust). A `.wasm` file is that compiled program. |
| **wasm-bindgen** | The tool that builds the two-way adapter between JavaScript and wasm. Rust values and JS values are different shapes; wasm-bindgen writes the glue that translates between them. It emits a `.wasm` file **plus** a `.js` file that knows how to load and talk to it. |
| **the facade crate** (`cockpit-wasm/`) | One special crate whose *only* job is to expose selected cockpit-crate functions to the browser. It's the front desk: JS knocks here, it calls the real crate behind it, and hands the answer back. "Facade" = a thin front over the real thing. |
| **the bridge** | The whole pipeline: facade crate → compiled wasm + glue → shared runtime → panel. "Bridging a crate" = adding a wrapper so that crate's logic is reachable from the browser. |
| **the runtime** (`cockpit-runtime.js`) | One shared JavaScript file every panel can opt into. It loads the wasm, offers helper functions, and — based on which panel it is — runs extra crate-powered features. |
| **panel** | One page of the dashboard, e.g. `d-06-pending-approvals`. Each panel is a single self-contained `index.html`. |
| **the demo / the full bridge** | Two builds of the same facade. The **demo** is tiny (banner logic only, ~128 KB) and is committed to git. The **full bridge** is large (all crates, ~3.8 MB) and is **not** committed — it's rebuilt on demand. Why: see §5. |

---

## 3. Why the bridge exists (the problem in one picture)

```
BEFORE                                  AFTER (with the bridge)

 Rust crate (the truth)                  Rust crate (the truth)
   AlertGroup::rollup()                    AlertGroup::rollup()
        │  used by the backend                  │  used by the backend
        │                                        │  AND compiled to wasm
        ▼                                        ▼
   backend / daemon                         backend / daemon        browser panel
                                                                         │
 browser panel                                                          │ calls the SAME
   sorts alerts in                                                       ▼ rollup() via wasm
   hand-written JS  ← can drift from the Rust!             one function, one source of truth
```

The audit (**F-2026-001**) found this was the single biggest gap in the codebase: **413 of the
418 cockpit crates were consumed by nothing that runs.** The operator chose to *build the
bridge* rather than delete the crates — make the browser actually run them.

---

## 4. The mental model: crate → wasm → runtime → panel

Follow one real feature end to end — the pending-approvals page rolling its approvals up by
severity:

```
 1. THE CRATE                     crates/sovereign-cockpit-alert-group/src/lib.rs
    Real Rust logic.              AlertGroup::observe(events).rollup()
                                  → groups events by tag, keeps the worst severity per group
        │
        │ a thin wrapper exposes it to the browser
        ▼
 2. THE FACADE WRAPPER            cockpit-wasm/src/compute/alert_group.rs
    Parses JSON in, calls the     #[wasm_bindgen]
    real crate, returns JSON.     pub fn alert_group_rollup(events_json) -> String
        │
        │ compiled by build.sh with wasm-bindgen
        ▼
 3. THE COMPILED ARTIFACT         webapp/_shared/cockpit-wasm/
    wasm program + JS glue.       cockpit_wasm_full_bg.wasm  (the program, 3.8 MB)
                                  cockpit_wasm_full.js       (the glue that loads it)
        │
        │ lazy-loaded on demand
        ▼
 4. THE SHARED RUNTIME            webapp/_shared/cockpit-runtime.js
    Loads the wasm once, offers   enhanceApprovals(): fetch live approvals →
    per-panel crate features.     alert_group_rollup(...) → draw a severity rollup
        │
        │ imported by one <script> tag
        ▼
 5. THE PANEL                     webapp/d-06-pending-approvals/index.html
    Opts in with one line;        <script type="module">
    the runtime does the rest.      import { enhance } from '/_shared/cockpit-runtime.js';
                                    enhance(document).catch(() => {});
                                  </script>
```

Every arrow is code that already exists. Adding a new crate feature means writing step 2
(a wrapper) and, if a panel should use it, a few lines in step 4.

---

## 5. How it's built

### 5.1 One facade, two builds — and why

The facade crate can be compiled two ways, controlled by a Rust **feature flag** named
`bridges` (a feature flag is just a switch that includes or excludes some code):

| Build | Switch | Contains | Size | Committed to git? |
|---|---|---|---|---|
| **demo** | (default, no switch) | banner logic only | ~128 KB | **yes** |
| **full bridge** | `--features bridges` | all 418 crates | ~3.8 MB | **no** (rebuilt on demand) |

Why split them:

- **The full 3.8 MB build is never committed.** Git should not carry a multi-megabyte binary
  that changes every rebuild. A lint test (`tests/lint/test_cockpit_wasm_bridge.py`) *enforces*
  a 600 KB ceiling on the committed file, so an accidental commit of the full build fails CI.
- **The committed demo proves the toolchain works** without shipping the big binary — anyone
  can clone the repo and see a real wasm module the banner page loads.
- **The full bridge is built locally when you need the crate features** (see §5.3). If it isn't
  built, panels still work — they just quietly skip the crate-powered extras (see §6.3).

### 5.2 The four tiers of bridge

Not every crate is exposed the same way. There are four tiers, in increasing richness:

| Tier | How many | What it exposes | Lives in |
|---|---:|---|---|
| **1. Banner (hand-written reference)** | 1 | `banner_severity`, `banner_state`, `banner_validate` — the original worked example | `cockpit-wasm/src/lib.rs` |
| **2. Uniform validate** | 398 | each crate's `validate()` — "is this state legal?" (returns `{ok, error}`) | `cockpit-wasm/src/bridges.rs` (auto-generated) |
| **3. Bespoke compute** | 19 | crates with no uniform `validate()` — each hand-wrapped over its real compute (color contrast, word count, pagination, relative time…) | `cockpit-wasm/src/bespoke/*.rs` |
| **4. Compute wrappers** | 12 | high-value crates' *derived output* — grouping, faceting, tree flattening, selection, state machines (not just "is it valid" but "what does it produce") | `cockpit-wasm/src/compute/*.rs` |

Tier 2 is generated by a script so 398 near-identical wrappers don't have to be typed by hand:

```
python3 cockpit-wasm/gen-bridges.py --count all
```

`gen-bridges.py` scans the crates, writes `src/bridges.rs` (one macro line per crate), keeps the
facade's `Cargo.toml` dependency list in sync, and writes `src/bespoke/mod.rs`. A lint test checks
the three stay consistent, so drift is caught automatically.

Tier 4 (the compute wrappers) reuses crates that are *already* in tier 2 — it adds a richer
export (e.g. `alert_group_rollup`) alongside the plain `alert_group_validate`. No new
dependencies; just more of each crate's real logic reachable.

### 5.3 The build commands

```
make cockpit-wasm        # builds the demo (committed) AND the full bridge (local, gitignored)
make cockpit-wasm-all    # builds + verifies the full family in a temp dir, writes nothing
SMOKE=1 make cockpit-wasm # demo build + run its exports in node as proof
```

Under the hood these call `cockpit-wasm/build.sh`, which:
1. runs the Rust compiler targeting `wasm32-unknown-unknown` (the "compile to WebAssembly" target),
2. runs `wasm-bindgen` to emit the `.wasm` + `.js` glue,
3. shrinks the wasm with `wasm-opt` (an optional size optimizer).

Requirements (one-time): `rustup target add wasm32-unknown-unknown` and
`cargo install wasm-bindgen-cli --version 0.2.100`.

> **To see the crate features light up in the browser, you must have run `make cockpit-wasm`
> locally** — that's what writes the full bridge the panels load. It's gitignored, so a fresh
> clone won't have it until you build it.

### 5.4 Why the facade lives *outside* the Rust workspace

If you look at the repo's root `Cargo.toml`, the facade is explicitly *excluded* from the
workspace. Two honest reasons:

- **The unsafe-code rule.** wasm-bindgen's generated glue contains `unsafe` Rust (low-level
  code the compiler can't fully check). The project keeps exactly **one** sanctioned unsafe crate
  (`sovereign-simd`). Excluding the facade keeps that promise literally true — the facade's own
  hand-written code stays fully safe; only the generated glue is unsafe, and it lives off to the side.
- **CI speed.** It keeps the browser/wasm toolchain off the main 700-crate build path.

---

## 6. How the runtime works

### 6.1 A panel opts in with one line

Every panel that wants crate features has exactly this before `</body>`:

```html
<script type="module">
  import { enhance } from '/_shared/cockpit-runtime.js';
  enhance(document).catch(() => {});
</script>
```

That's the whole contract. `enhance(document)` runs; if anything fails (wasm missing, etc.), the
`.catch(() => {})` swallows it and the page is unaffected.

### 6.2 What `enhance()` does

`cockpit-runtime.js` exposes a handful of helpers — `bridge()` (loads the wasm once),
`contrast()`, `relTime()`, `wordCount()`, `truncate()`, `validate()`, `auditPalette()`, and
`enhance()`. When a panel calls `enhance()`:

1. **Universal pass** — every panel gets a WCAG accessibility badge (real color-contrast crate
   checking the page's own color tokens) and human-readable "3 minutes ago" timestamps.
2. **Per-panel pass** — the runtime reads the panel's `<meta name="x-sovereign-module">` tag and,
   if there's a matching *enhancer* registered, runs it. Examples wired today:
   - `d-06-pending-approvals` → **alert-group** rolls the live approvals up by severity and draws
     that rollup, so the crate now does the grouping the panel used to hand-roll in JS. (It's added
     *alongside* the panel's own sort, which stays as the offline-safe baseline — see §6.3.)
   - `models-catalog` → **facet-counts** groups the live model list into top buckets per facet.

### 6.3 It always degrades honestly

Every crate feature is **additive and graceful**. If the full bridge isn't built, or a data
endpoint is down, the enhancer simply does nothing — no error, no broken page. This is the
"panels always work offline" doctrine: the crate logic is an enhancement layered on top of a page
that already stands on its own.

---

## 7. A worked example, top to bottom

**Goal:** the pending-approvals page should group its approvals by severity using the real
`alert-group` crate — the same grouping it used to do by hand in JavaScript — added as a
crate-computed section on top of the existing page.

1. **The crate** (`sovereign-cockpit-alert-group`) already knows how: `observe()` each event, then
   `rollup()` groups them by tag and keeps the worst severity + latest timestamp per group.
2. **The wrapper** (`cockpit-wasm/src/compute/alert_group.rs`) exposes it:
   `alert_group_rollup(events_json)` — parse a JSON array of `{tag, severity, ts_ms}`, run the real
   crate, return `{ok, total, groups:[{tag, count, max_severity, latest_ts_ms}]}`. It never panics;
   bad input returns an error object.
3. **The build** (`make cockpit-wasm`) compiles it into `cockpit_wasm_full_bg.wasm` and exports
   `alert_group_rollup` in `cockpit_wasm_full.js`.
4. **The runtime** (`cockpit-runtime.js`, `enhanceApprovals`) fetches the live approvals, maps each
   to `{tag, severity, ts_ms}`, calls `alert_group_rollup(...)`, and draws a small "N pending across
   M groups" rollup section.
5. **The panel** (`d-06-pending-approvals/index.html`) does nothing new — it already has the
   one-line `enhance()` opt-in and the `x-sovereign-module` meta tag, so the runtime finds and runs
   the enhancer automatically.

You can watch all of this live on the **`/crates` surface** (`webapp/_shared/cockpit-wasm/crates.html`):
it loads the full bridge and has an editable box for each of the 12 compute wrappers — change the
input JSON and the real crate recomputes on every keystroke.

---

## 8. Recipes

### 8.1 Expose a new crate's `validate()` (tier 2)

Usually automatic — add the crate, then:

```
python3 cockpit-wasm/gen-bridges.py --count all
cd cockpit-wasm && cargo fmt
make cockpit-wasm-all      # verify the whole family still builds + runs
```

### 8.2 Expose a crate's real *compute* (tier 4)

1. Add `cockpit-wasm/src/compute/<crate>.rs` with a `#[wasm_bindgen] pub fn <crate>_<verb>(json) -> String`
   that parses the crate's type, calls its real method, and returns JSON. **Never panic** — return an
   `{ok:false, error}` object on bad input instead.
2. Add `pub mod <crate>;` to `cockpit-wasm/src/compute/mod.rs`.
3. `cd cockpit-wasm && cargo fmt && cargo clippy --features bridges && cargo test --features bridges`.
4. `make cockpit-wasm` to rebuild the full bridge.
5. (Optional) verify it runs from the built artifact in node before wiring a panel.

### 8.3 Make a panel use a crate feature

1. Ensure the panel has the `enhance()` opt-in script and a `<meta name="x-sovereign-module" content="<panel>-webapp">` tag.
2. In `cockpit-runtime.js`, write an `async function enhance<Thing>(root)` that fetches the panel's
   live data, calls the wrapper via `bridge()`, and appends a result section. Keep it **additive and
   graceful** (return early on any failure).
3. Register it in the `ENHANCERS` map keyed by the panel's module name.

### 8.4 Rebuild + verify everything

```
make cockpit-wasm                                   # rebuild demo + full bridge
cd cockpit-wasm && cargo fmt --check && \
  cargo clippy --features bridges && \
  cargo test --features bridges                     # Rust gates
python3 -m pytest tests/lint/test_cockpit_wasm_bridge.py -q   # the bridge contract
```

---

## 9. Where everything lives

```
cockpit-wasm/                              the facade crate (OUTSIDE the workspace)
├── src/lib.rs                             tier 1: banner reference + the bridge_validate! macro
├── src/bridges.rs                         tier 2: 398 generated validate() wrappers
├── src/bespoke/*.rs                       tier 3: 19 hand-written compute bridges
├── src/compute/*.rs                       tier 4: 12 derived-output compute wrappers
├── gen-bridges.py                         regenerates tiers 2 + 3's plumbing
└── build.sh                               compiles the demo and/or the full bridge

webapp/_shared/cockpit-wasm/
├── cockpit_wasm.js / _bg.wasm             the committed DEMO (banner only, ~128 KB)
├── cockpit_wasm_full.js / _bg.wasm        the FULL bridge (gitignored, ~3.8 MB, built on demand)
├── demo.html                              the banner demonstrator (loads the demo)
└── crates.html                            the /crates surface (loads the full bridge; every crate runs here)

webapp/_shared/cockpit-runtime.js          the shared runtime every panel opts into
webapp/<panel>/index.html                  each panel: one-line enhance() opt-in + module meta tag

scripts/operator/cockpit-bridge-api.py     read-only server (loopback :8137) that serves the webapp,
                                           the wasm (as application/wasm), and live signal JSON
systemd/system/sovereign-cockpit-bridge-api.service   the unit that runs that server

tests/lint/test_cockpit_wasm_bridge.py     the contract lint that keeps all of the above honest
```

---

## 10. Common questions

**Why not just rewrite the panels in Rust?** The panels are deliberately plain, self-contained HTML
that work with no build step and no network. The bridge keeps that property — it *adds* real Rust
logic as an optional enhancement, without turning the webapp into a compiled front-end app.

**Why is the big bridge not in git?** It's a 3.8 MB binary that changes on every rebuild; committing
it would bloat history and slow every `git` operation. It's cheap to rebuild (`make cockpit-wasm`), so
it's treated as a build product, not source. A CI test blocks it from ever being committed by accident.

**Do panels break if the wasm is missing?** No. Every crate feature is wrapped so that a missing
bridge or a failed load is a silent no-op. The page always renders on its own first.

**Is this "done"?** The bridge and all four tiers are in place, and the first panels are wired. The
ongoing work is adopting more crates inside more panels — each one is now "write a small enhancer,"
not "invent an architecture."
