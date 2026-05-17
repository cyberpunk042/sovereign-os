# SDD-030 — Operator-overlay doctrine (E5.M11 / R283)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E5.M11 (mandate decomposition)
> Derived from: §1a of operator mandate ("endless flexibility and
> fine-tuning and adapting possible")

## Mission

§1a of the operator mandate explicitly calls for "endless flexibility
and fine-tuning and adapting possible" — every script must accept
operator-supplied TOML overlays that layer on top of in-source
defaults, WITHOUT each script reinventing the loader.

SDD-030 codifies the shared `scripts/lib/operator_overlay.py` helper
+ the adoption doctrine + the env-var naming convention.

## Doctrine

### 1. Single import per consumer script

```python
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
from operator_overlay import load_with_overlay

DEFAULTS = {
    "threshold_pct": 25,
    "limits": {"warn": 100, "critical": 200},
}

def my_main(...):
    cfg = load_with_overlay("my-script", DEFAULTS)
    # cfg is DEFAULTS deep-merged with operator overlay (if any).
    # cfg["_source"] tells the operator which file (or "(defaults)").
    # cfg["_overlay_keys"] lists dotted-paths overridden.
```

### 2. Path resolution precedence

`load_with_overlay("my-script", ...)` looks at these locations in order:

1. `explicit_path` arg (e.g. `--config` flag passed by operator)
2. `$SOVEREIGN_OS_OVERLAY_MY_SCRIPT` env var (capitalized; `-`→`_`)
3. `/etc/sovereign-os/my-script.toml`
4. `config/my-script.toml.example` (dev fallback)
5. None → defaults pass through with `_source = "(defaults)"`

### 3. Deep-merge semantics

- **Scalars** (int, str, float, bool, None): operator value REPLACES default.
- **Nested dicts**: recursively merged — operator's nested key wins,
  sibling defaults preserved.
- **Lists**: REPLACED entirely (NOT concatenated) so operator can
  clear a default list by setting `key = []`.

This is the "operator-key-wins" rule. Operator gets veto authority
on every default the script ships.

### 4. Audit metadata

Every merged config carries:

- `_source` — overlay path used, or `"(defaults — no overlay file)"`
- `_overlay_keys` — sorted list of dotted-path keys overridden by TOML
- `_parse_error` (only when TOML is malformed) — error string for the
  operator to see; defaults still apply, script does NOT crash.

This means EVERY consumer script's `--json` output can surface which
operator knob is active, making support runs trivial: "what's
overridden on your host? show me `<verb> status --json | jq
._overlay_keys`."

### 5. Robust failure mode

Malformed TOML → defaults apply + `_parse_error` set. Script never
crashes from a bad overlay. Operator audits by checking the field;
support reproduces by reading the file.

## Adoption checklist for a new consumer

1. Add the import block (3 lines).
2. Move config defaults from scattered argparse defaults / inline
   constants into a single `DEFAULTS = {...}` dict at module scope.
3. Replace existing config-load logic with `cfg = load_with_overlay(
   "<script-name>", DEFAULTS, explicit_path=args.config)`.
4. Ship a `config/<script-name>.toml.example` documenting the knobs
   + the master-spec / mandate anchor that motivated each.
5. Surface `cfg["_source"]` and `cfg["_overlay_keys"]` in --json
   output so operators see which overlay is active.

## L1 lint guard

`tests/lint/test_operator_overlay.py` pins the public API + deep-
merge semantics + env-var naming + parse-error fallback. Any future
refactor that breaks the contract is caught at L1 before push.

## Future-round adoption candidates

- `kernel/tuning.py` — already loads TOML; refactor to use the helper.
- `power-status.py` — same.
- `ram-advisor.py` — recently shipped; uses tomllib directly.
- `bios-info.py` — KNOWN_BOARDS TOML loader.
- `notify/dispatch.py` — channel config.
- `dashboard/serve.py` — auth config.
- `kernel-tuning.toml.example` — kept; doctrine just changes loader.

Each adoption is a separate round (one-script-per-round to keep
diffs small + L3 tests in lockstep). Adoption order is operator-
preference-driven; the doctrine doesn't force a sequence.

## What this SDD does NOT cover

- TOML schema validation per-script (left to each consumer; helper
  is schema-agnostic).
- Operator-supplied config encryption (out of scope; if needed,
  belongs to a SDD-009 sibling).
- Runtime hot-reload (helper loads once per script invocation; long-
  running daemons that need reload signal SIGHUP and reload by
  re-invoking `load_with_overlay`).
