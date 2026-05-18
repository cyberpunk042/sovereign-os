# SDD-038 — Cross-repo binding doctrine (sovereign-os ↔ selfdef)

> Status: review
> Owner: operator
> Last updated: 2026-05-18
> Closes findings: none (formalizes R460-R469 implementation arc)
> Derived from: operator-§1g/§1h "two ultimate solutions" perpetual mandate

## Mission

Two repositories — `cyberpunk042/sovereign-os` (operator-facing
OS-image-pipeline + §1g compliance instrument suite) and
`cyberpunk042/selfdef` (host self-defense service with module
catalog) — are the operator's "two ultimate solutions". They MUST
co-progress under the perpetual dual-repo mandate without drifting
on operator-named taxonomies.

This doctrine formalizes the **typed-TOML-manifest** pattern proven
across 5 implementation rounds (R460/R462/R464/R465/R466) and the
end-to-end acceptance test that exercises all 5 simultaneously
(R469).

## Problem

Operator-named taxonomies — auth tiers (6), §1g surfaces (8), UX
dimensions (6), minimization patterns (8), event-status enum — must
be **identical** across both repos. Without a mechanized binding:

- A selfdef module declaring `auth_tier = "moderate"` produces silent
  data loss when sovereign-os tries to plot it against the 6-tier
  ladder.
- A sovereign-os surface-map gap report against a stale taxonomy
  miscounts which §1g surfaces are missing.
- An anti-minimization audit reading selfdef's reported findings
  against a drifted pattern catalog flags wrong patterns.

Documentation-only "both repos agree" is insufficient — humans drift
on long-tail constants. The binding must be **enforced at compile
time** on the producer side AND **defense-in-depth re-validated** on
the consumer side.

## Required coverage

A1. Every operator-named taxonomy SHOULD have ONE source-of-truth
location (sovereign-os script-side const or schema) and a typed
mirror on the selfdef side (Rust crate with const + serde derive +
unit test asserting exact-order match).

A2. The wire format between repos MUST be operator-readable
(TOML preferred; JSONL for event streams). No binary or
project-specific encodings.

A3. The consumer (sovereign-os) MUST re-validate every field
defensively — never trust the producer (selfdef). A drifted
producer surfaces as an `errors[]` entry the operator sees, not
silent ignore.

A4. The binding MUST be exercised in at least one end-to-end
acceptance test (R469-style: synthesized fixture → consumer
invocation → field-level assertion).

## Goals

G1. Drift on either side fails tests on **BOTH** sides — selfdef
unit-test of `assert_eq!(TIER_NAMES, [...])` fails when selfdef
edits the array; sovereign-os end-to-end test fails when either
side renames a field.

G2. New cross-repo bindings follow the same shape: NEW crate
`selfdef-<name>-manifest` exporting public consts +
`from_toml_str()` + `validate()` + ≥10 unit tests; NEW sovereign-os
verb `<existing-tool> selfdef` consuming the TOMLs with defense-
in-depth re-validation + ≥5 L1 lint assertions.

G3. Operators with both repos cloned get one-command rollups:
`sovereign-osctl compliance status` for state visibility +
`sovereign-osctl bashrc combo` for one-shot install.

## Non-goals

- This doctrine does NOT cover dynamic feature negotiation between
  the daemons at runtime. The bindings are static-state TOMLs +
  append-only event streams; live RPC stays out of scope.
- Selfdef internal architecture (collectors, correlator, modules)
  is not constrained by this doctrine. Only the operator-facing
  cross-repo surface is bound.

## Open questions

| ID | Question | Resolution |
|----|----------|------------|
| Q-038-001 | Should we ship a single workspace dep crate (`selfdef-cross-repo-prelude`) that re-exports all 6 typed mirrors? | **deferred** — premature consolidation; each mirror is consumed by exactly one selfdef use site so per-crate deps are clearer. |
| Q-038-002 | Should sovereign-os also publish a Python pip-installable package of the consumer verbs? | **deferred** — current shell invocation pattern (`python3 scripts/operator/<tool>.py`) is operator-§1g-aligned (no hidden install state); revisit if fleet-deployment requires it. |
| Q-038-003 | Are versioned schemas needed (TOML `schema_version` field)? | **answered (R460+, schema_version=1)** — every cross-repo TOML carries `schema_version = 1`; future breaking changes bump to 2 with consumer-side reject of unknown versions. |

## Way forward

### Binding shape (canonical)

On the **selfdef side**, a new cross-repo binding is a Rust crate at
`crates/selfdef-<name>-manifest/` with:

```rust
pub const SCHEMA_VERSION: u32 = 1;
pub const TAXONOMY: [&str; N] = [/* operator-§1g verbatim order */];

pub struct Manifest {
    pub schema_version: u32,
    pub module: ModuleHeader,
    pub <items>: Vec<Entry>,
}

pub fn from_toml_str(s: &str) -> Result<Manifest, Error>;
pub fn from_toml_path<P: AsRef<Path>>(p: P) -> Result<Manifest, Error>;
pub fn validate(m: &Manifest) -> Result<(), Error>;
```

Plus unit tests:
- `taxonomy_matches_sovereign_os_<round>_verbatim_order` (the
  drift-detection sentinel; pins the exact `[N]` array).
- `parses_well_formed`, `rejects_unknown_<field>`,
  `rejects_duplicate_<key>`, `rejects_future_schema_version`,
  `round_trips_via_serde`.

On the **sovereign-os side**, a new verb on the existing instrument
script at `scripts/operator/<tool>.py`:

```python
SELFDEF_<TAXONOMY>_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_SELFDEF_<TAXONOMY>_DIR",
        "/etc/selfdef/<taxonomy>/",
    )
)

def load_selfdef_<taxonomy>_manifests() -> tuple[list, list]:
    # tomllib with tomli py3.10 fallback
    # per-manifest validate schema_version + module.id + items[]
    # rejects unknown <fields> (defense-in-depth; selfdef-side
    # validation already enforces but consumer never trusts producer)
    # tag each entry source_repo='selfdef' + manifest_path
    ...

def cmd_selfdef(args) -> int:
    # JSON + human output
    # emits metric: <tool>_query_total{verb,...,result}
    ...
```

Plus L1 lint assertions in `tests/lint/test_<tool>_contract.py`:
- `test_supports_selfdef_verb` (with `SD-R-<NAME>-1` reference)
- `test_selfdef_<taxonomy>_dir_env_overridable`
- `test_selfdef_default_<taxonomy>_dir`
- `test_selfdef_verb_smoke` (end-to-end with fixture)
- `test_selfdef_verb_rejects_<negative-case>`

### Currently-bound taxonomies (R460-R466)

| Cross-repo ID                  | Sovereign-os round            | Selfdef crate                  | Mirrored taxonomy           |
|--------------------------------|-------------------------------|--------------------------------|-----------------------------|
| `SD-R-DASHBOARD-MANIFEST-1`    | R460 master-dashboard discover| selfdef-dashboard-manifest     | 6-tier auth + 8-surface     |
| `SD-R-EVENT-LOG-1`             | R465 global-history env-fix   | selfdef-history-sink           | 5-state event-status enum   |
| `SD-R-AUTH-TIER-1`             | (transitively via R460)       | selfdef-auth-tier              | 6-tier ladder (typed enum)  |
| `SD-R-MULTI-SURFACE-AUDIT-1`   | R462 surface-map selfdef      | selfdef-surface-manifest       | 8-surface §1g taxonomy      |
| `SD-R-UX-CHECKLIST-1`          | R464 ux-design-audit selfdef  | selfdef-ux-checklist           | 6-dimension UX-quality enum |
| `SD-R-AUDIT-1`                 | R466 anti-min-audit selfdef   | selfdef-audit-manifest         | 8-pattern minimization      |
| `SD-R-BASHRC-1`                | R468 bashrc-install combo     | selfdef-bashrc-install         | sentinel-bounded bashrc     |

### End-to-end acceptance (R469)

`tests/lint/test_cross_repo_compliance_end_to_end.py` codifies the
acceptance criterion as a single test: synthesize a complete selfdef
deployment fixture → run `compliance status --json` → assert all 5
cross-repo binding paths report correct data simultaneously +
recovery semantics + defense-in-depth schema rejection.

### Operator-DX rollups (R458 + R468)

- **One-command STATUS**: `sovereign-osctl compliance status` shows
  8 instruments (4 sovereign-os internal + 4 selfdef-discovery axes).
- **One-command INSTALL**: `sovereign-osctl bashrc combo` chains
  the sovereign-os bashrc installer + the selfdef bashrc installer.

Both rollups embody operator-§1h "high UX/DX" — reduce the operator's
action-budget from N commands to 1.

## Cross-references

- Sovereign-os: scripts/operator/{master-dashboard,surface-map,
  ux-design-audit,anti-minimization-audit,global-history,compliance,
  bashrc-install}.py
- Selfdef: crates/selfdef-{dashboard-manifest,history-sink,auth-tier,
  surface-manifest,ux-checklist,audit-manifest,bashrc-install}/
- End-to-end acceptance: tests/lint/test_cross_repo_compliance_end_to_end.py
- Operator-mandate: docs/standing-directives/2026-05-17-operator-mandate.md
  (E11.M1 through E11.M12)
- Sister doc on selfdef side:
  cyberpunk042/selfdef:README.md § "Cross-repo binding"
