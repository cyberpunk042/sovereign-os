# SDD-510 — Token-law mask-layer selection: the operator-configurable layer knob (profile + env + CLI)

> Status: active · Mandate: **E11.M510** (control-bits band 500–599)
>
> Cross-link: continues the **M00155 operator surface** (`backlog/milestones/M010-deterministic-data-plane.md`, F00793/F00794/F00795) over the M00117 engine. The ninth SDD in the control-bits band, and the **second of the Expose arc** (after SDD-507, which shipped F00792/F00797/F00798).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"we continue"* → the token-law Expose fork). SDD-507 opened the fusion route but the *which layers are active* selection was hard-wired to "all present sources." This ships the three operator-configurable surfaces the milestone specs: the **profile knob** (F00793), the **env var** (F00794), and the **CLI verb** (F00795).

## Mission

The M00117 engine fuses up to five named laws per decode step —
`grammar` (JSON-schema→grammar), `regex`, `denylist`, `regex_denylist`, and the
static `policy` planes. SDD-507's fusion route (`POST /v1/data-plane/token-law/fuse`)
activated a layer whenever its *source* was supplied. The M00155 milestone
specs an operator control on top of that: **which of those layers are active** —
so an operator can dial the engine down to (say) `safety` only, or turn the
grammar plane off, **without changing the request**. Three surfaces:

- **F00793** — profile knob `token_law_engine_mask_layers = grammar,schema,tool,safety`
- **F00794** — env var `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`
- **F00795** — CLI `--token-law-mask-layers <csv>`

## The layer vocabulary — real planes + milestone aliases

The engine's **real** plane names are `grammar` / `regex` / `denylist` /
`regex_denylist` / `policy` (what `FuseRequest::layers_active` reports, what the
`sovereign_data_plane_token_law_mask_layers` metric counts). The milestone's
conceptual names (`grammar,schema,tool,safety`) are accepted as **aliases** so
the operator-facing csv matches the spec:

| Operator name | Canonical plane(s) |
|---|---|
| `grammar`, `schema` | `grammar` (the JSON-schema→grammar plane) |
| `tool`, `regex` | `regex` (a tool-call allow-list is a `(a\|b\|…)` alternation) |
| `safety` | `denylist` + `regex_denylist` |
| `policy` | `policy` (static bitset planes) |

An empty/unset selection ⇒ **all layers active** (unchanged behavior — SDD-507
callers see no difference until they configure a selection).

## Design

### 1. The selection primitive — `MaskLayerSet` (`sovereign-token-law-fuse`)

A `Copy` struct of five bools with:
- `from_csv` / `from_names` — parse real names or aliases (case-insensitive), `safety`→both denials, empty⇒all, unknown⇒`FuseError`;
- `from_env_or_all` — read `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`, else all (the impure boundary; the pure fuse core takes a resolved selection);
- `names()` — the active canonical names in fuse order.

`FuseLayers::select(&sel)` returns a copy with every **deselected** layer cleared
(no allocation — cleared slices become the empty slice, `schema`/`regex` become
`None`), so a skipped layer contributes nothing to the fuse even when its source
is present.

### 2. The request honors it — `FuseRequest.mask_layers`

`FuseRequest` gains `mask_layers: Option<Vec<String>>` (absent⇒all). `fuse()`
resolves the selection and applies `select` before compiling; `layers_active()`
now reports a layer only when its source is present **and** the selection keeps
it. The pure core stays deterministic — env/flag defaults are resolved by the
caller.

### 3. The surfaces resolve the precedence

**Precedence: `--token-law-mask-layers` flag > `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`
env > the active runtime profile's `token_law_engine_mask_layers` knob > all.**

- **The gateway route** (`token_law_fuse`, `crates/sovereign-gatewayd/src/http.rs`):
  when a request omits `mask_layers`, it fills the operator's env selection
  (`from_env_or_all`) — so a raw HTTP client gets the configured default. An
  explicit request selection always wins.
- **The osctl verb** (`sovereign-osctl token-law`, `scripts/operator/token-law-cli.py`):
  - `token-law layers [--token-law-mask-layers CSV] [--json]` — resolve + print
    the active selection and which source won (needs **no daemon** — pure config
    introspection);
  - `token-law fuse --vocab … [layer sources] [--token-law-mask-layers CSV] [--json]`
    — POST a `FuseRequest` (with the resolved selection) to the sanctioned route
    and print the fused mask, active layers, allowed count, per-layer coverage,
    and stop flag. Degrades cleanly when the gateway is down.
- **The profile knob** — `token_law_engine_mask_layers` on the runtime-profile
  schema (a csv string or a list); the shipped `high-concurrency-burst` profile
  pins the milestone default `grammar,schema,tool,safety`. The osctl verb reads
  the active profile (`SOVEREIGN_OS_RUNTIME_PROFILE`) for its default.

## What shipped

- **`crates/sovereign-token-law-fuse`** — `MaskLayerSet` (parse / env / names),
  `FuseLayers::select`, `FuseRequest.mask_layers` + selection-aware `fuse()` /
  `layers_active()`. +4 crate tests (parse real+alias+empty+unknown, select
  skips a supplied layer, selecting an absent layer is a no-op). Pure stdlib;
  `forbid(unsafe_code)` preserved.
- **`crates/sovereign-gatewayd`** — the fuse route applies the env selection when
  the request omits one (F00794 server-side). Metric unchanged.
- **`scripts/operator/token-law-cli.py`** + the `token-law` dispatch — the osctl
  verb (F00795). Full registration chain: dispatch case + COMMANDS help +
  `feature-coverage.yaml` cli-only waiver (dashboard home = the F00796 heatmap,
  the next Expose SDD) + `models` man-topic ownership with a `## token-law` /
  `.SS token-law` section.
- **`schemas/runtime-profile.schema.yaml`** + `profiles/runtime/high-concurrency-burst.yaml`
  — the `token_law_engine_mask_layers` knob (F00793).
- **Tests** — `tests/lint/test_token_law_cli.py` (precedence flag>env>profile>all,
  aliases, unknown rejected, fuse-degrades-when-down, dispatch pins) + the crate
  tests. The osctl verb-chain lints (manpage / discovery / feature-coverage /
  dx-help / verb-dispatch) + the runtime-profile schema lint stay green.

## Non-goals / roadmap

- **F00796 dashboard** — the token-law mask-coverage heatmap — is the **next
  Expose SDD (511)**; this SDD is CLI/config-first (the verb's cli-only waiver
  points at it).
- A gatewayd `--token-law-mask-layers` **daemon** flag is not shipped — the env
  var is the daemon-side control; the flag lives where the milestone puts it, on
  the operator CLI.
- **Connect** (`/v1/messages` serving boundary) and **Deepen** (the remaining
  M00117 planes) continue the fork in later SDDs.

## References

- Milestone rows: `backlog/milestones/M010-deterministic-data-plane.md` F00793/F00794/F00795 (rules R01623 mask-layers-operator-configurable, R01660 CLI flag; M00155).
- Opener: `docs/sdd/507-token-law-fusion-data-plane.md` (F00792/F00797/F00798).
- Engine: `crates/sovereign-token-law-fuse/src/lib.rs`; `crates/sovereign-llm/src/lib.rs` (`TokenLawSpec`, `complete_with_token_law`).
- Route: `crates/sovereign-gatewayd/src/http.rs` (`token_law_fuse`).
