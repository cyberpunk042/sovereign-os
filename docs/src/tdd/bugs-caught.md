# Bugs caught by Layer 1/2/3 discipline

A running ledger of real wiring bugs caught by the 5-layer TDD pyramid
(SDD-008). Most early entries (bugs 1-10) surfaced ONLY in Layer 3
nspawn-style tests despite passing L1 + L2. Later bugs (#14-17) were
caught by Layer 1 lint (hook coverage gates) and Layer 2 contract
tests (--json schema, SDD-stated invariants).

Running tally: **17 bugs caught** as of Round 130. Each surfaced + fixed
+ pinned by a test that prevents the regression class.

Operationally important: 5 of these bugs belong to the
shell-var-vs-exported-env propagation class (Learning 1). The
SDD-stated-invariant-without-code-guard class (bugs #15 + #17,
Learning 4) is now the second-largest. Test patterns themselves are
the third bug surface (bug #7 regex bug; bug-class noted under
Learning 5 about test pattern pluralization).

## The ledger

| # | Component | Symptom | Fix | Surfaced by |
|---|---|---|---|---|
| 1 | `whitelabel/default.yaml` template paths | render engine emitted no file with "template not found" warning | absolute paths under `default/` not relative to `whitelabel/` | `test_whitelabel_render_to_disk.sh` |
| 2 | `orchestrate.sh` cmd_help | `sed '1,/^Usage:/!d'` truncated Commands / Steps / Env-vars sections | `sed -n '/^[^#]/q; s/^# \?//p'` | `test_orchestrator_status.sh` |
| 3 | `state_step_status` empty-string default | awk no-match exited 0 with empty stdout instead of "pending" | `echo "${result:-pending}"` | `test_state_lib.sh` |
| 4 | `logging.sh` log_file parent dir | `__log_emit` failed when log dir didn't exist | lazy `mkdir -p "$(dirname …)"` | `test_common_lib.sh` |
| 5 | `sovereign-osctl profiles list` shell-var-vs-export | `SOVEREIGN_OS_PROFILE_FILE="$p" name="$(profile_field …)"` didn't propagate to python3 subshell → silent empty rows | explicit `export SOVEREIGN_OS_PROFILE_FILE="$p"` before profile_field calls | `test_sovereign_osctl.sh` |
| 6 | `friction-audit-spec.sh` bash -c profile_field | `bash -c '… $(profile_field …) …'` — bash function not visible in fresh subshell | pre-compute the value in outer shell where profile_field is in scope, pass the string to test | preflight L3 against minimal |
| 7 | `test_decisions_log_sequence.py` regex | `^## D-` never matched actual `### D-` entries → monotonic-ordering test passed vacuously | regex relaxed to `^#{2,3} D-`; ordering exposed + reordered | adding 4th decision entry |
| 8 | `first-login-assistant.sh` unconditional hostnamectl | failed in containers without systemd-as-PID-1 (`System has not been booted with systemd…`) | graceful fallback: hostnamectl → `/etc/hostname` → `log_warn` | `test_first_login_assistant.sh` |
| 9 | inference start scripts `${VAR:=…}` defaults | not exported → inline `python3` saw empty `os.environ`, KeyError at startup | explicit `export PULSE_*` / `LOGIC_*` / `ORACLE_*` after defaults | `test_inference_start_scripts.sh` |
| 10 | `sovereign-osctl doctor` missing load_profile | profile_field returned 'unknown' → ALL profile-conditioning inert; sain-01 doctor ≡ minimal doctor | early `load_profile "${SOVEREIGN_OS_PROFILE}"` in cmd_doctor | `test_sovereign_osctl_doctor_v2.sh` |
| 11 | `sovereign-osctl models remove` `${1:?word}` brace ambiguity — usage text embedded `\${SOVEREIGN_OS_MODELS_DIR}` inside `:?word`; bash absorbed trailing `)}` into `$1` → "model not resident" with corrupted path | replaced `${1:?text}` with explicit `${1:-}` + `if [ -z … ]` + `log_error` + `return 2` (quote-safe regardless of message content) | `test_sovereign_osctl_models.sh` |
| 12 | `sovereign-osctl` lib-path mismatch — looked only at `/usr/lib/sovereign-os/` but `make install PREFIX=/usr/local` (default) installs to `/usr/local/lib/sovereign-os/`. Operators using the default install workflow would get "can't locate its lib" on first invocation | 5-candidate ordered lookup (`SOVEREIGN_OS_LIB` env > in-repo > `/usr/local/lib` > `/usr/lib` > `/opt`) with operator-actionable error listing all candidates | `test_sovereign_osctl_lib_paths.sh` |
| 13 | `live-build-emit.sh` README.md embedded `$(basename "${out_dir}")` — the tmpdir's unique name leaked into the emitted README, making the adapter non-reproducible (same inputs → different outputs across runs because the tmpdir name differed). SDD-019 reproducibility violation | replaced the embedded basename with literal `<this dir>` placeholder in the README's build-recipe line | `test_reproducibility_self_test.sh` |
| 14 | `first-login-assistant.sh` missing Layer B emission — every other lifecycle hook (17/18) called `emit_metric` for pass/fail; this one shipped without observability so fleet operators were blind to whether the post-install assistant ran, was skipped, or completed. Silent gap, never tripped any existing test | sourced `observability.sh` + added 3 emit_metric calls (skipped-fast-path, completed counter, choices gauge) AND authored Layer 1 lint `test_hook_layer_b_coverage.py` parametrizing over every hook script, asserting emit_metric is present or an explicit `# LAYER-B-WAIVER:` is recorded — closes the regression class | `test_hook_layer_b_coverage.py` |
| 15 | `cmd_alerts` rule engine reacted to `sovereign_os_meta_*` metrics — Rule 6 (stale `*_last_run_timestamp`) matched `sovereign_os_meta_alerts_check_last_run_timestamp` from the alerts-check hook output, creating a self-reinforcing alert loop on every hourly tick. SDD-023 § Meta-observability EXPLICITLY said this MUST NOT happen ("alerts-check hook's meta metrics MUST NOT trigger rules") but the code didn't enforce the rule — only the comment in the SDD. Silent bug in production until the Layer 2 schema test was authored | added explicit `if name.startswith("sovereign_os_meta_"): continue` guard at the top of the rule engine's parse loop (before any rule application). The L2 test (`test_no_meta_metrics_trigger_rules`) writes a synthetic meta .prom file and asserts no alert references a meta_* metric | `test_alerts_json_schema.py::test_no_meta_metrics_trigger_rules` |
| 16 | `schemas/mixin.schema.yaml` referenced but missing — every one of the 6 mixin YAML files under `profiles/mixins/` declared `# yaml-language-server: $schema=../../schemas/mixin.schema.yaml` to enable editor-side validation. The schema file DID NOT EXIST. Editor validation silently failed → no IDE-side type checking on mixin authoring → mistakes (wrong types, missing required keys, malformed hooks) went uncaught until orchestrator runtime. Caught while spelunking the schemas/ dir for Round 124 substantive work | authored `schemas/mixin.schema.yaml` (Draft 2020-12) reverse-engineered from the on-disk shape of the 6 existing mixins. Added `tests/schema/test_mixin_schema_conformance.py` with 20 assertions: schema file present + each mixin validates + mixin.id matches filename + every mixin has the language-server directive pointing at the schema | `test_mixin_schema_conformance.py` |
| 17 | `whitelabel/render.py` line-replace required template/content despite the operation not needing them — `/etc/default/grub` surface declared `strategy: template-substitution` + `operation: line-replace` + `pattern` + `replacement` but NO `template` and NO `content`. The render engine's template-substitution path warned `surface /etc/default/grub has no template/content` and `continue`'d before reaching the line-replace branch. Result: the line-replace action was SILENTLY DROPPED from the changeset; the substrate adapter never saw it; the deployed system shipped without the GRUB whitelabel edit. Caught noticing the recurring warning in `make ci` output during Round 129 verification | restructured the template-substitution path to handle `operation: line-replace` FIRST (before requiring template/content), since line-replace's pattern+replacement is the whole declaration. Standard template-substitution path continues to require template/content. Added L2 regression gate `test_line_replace_operation_does_not_require_template_or_content` asserting both the action is recorded AND no spurious "no template/content" warning fires | `test_whitelabel_render.py::test_line_replace_operation_does_not_require_template_or_content` |

## Project learnings

### Learning 1 — shell-var-vs-exported-env (bugs 5 + 6 + 9 + 10)

**Class:** scripts that set `${VAR:=default}` or `VAR=foo cmd …` defaults
without `export`-ing, then invoke `python3 -c …` (or `bash -c …`) that
expects to read the value via `os.environ`. Python's subshell only
sees EXPORTED env, not bash shell vars.

**Why it slips past Layer 1+2:**
- Layer 1 (schema/lint) doesn't touch the runtime export-set
- Layer 2 (unit) typically mocks the env or calls the function
  directly in-process — never re-exec's a child process

**Why Layer 3 catches it:**
- L3 tests invoke the actual script as a child process
- Child process inherits ONLY exported env
- Anything the script depended on being implicitly there gets the
  empty string + behavior diverges from author intent

**Fix pattern:**
```bash
: "${MY_VAR:=default}"
export MY_VAR                  # ← THIS line
# Or, inline:
: "${MY_VAR:=default}" && export MY_VAR
```

**Test pattern:**
```bash
# Run script via 'script.sh' (not '. script.sh') in the L3 test
out="$("${script}" 2>&1)"
# Assert on visible behavior, not function-level state
```

### Learning 2 — pipefail + grep -q SIGPIPE-kills upstream (rounds 29, 35, 55)

**Class:** `set -o pipefail` + `cmd | grep -q PATTERN` where cmd
produces output that grep matches early — grep exits 0 and closes
the pipe; cmd gets SIGPIPE (exit 141); pipefail reports the pipe
as failed; `if` takes the else branch even though the pattern WAS
present.

**Fix pattern:**
```bash
# Capture-then-grep
out="$(cmd 2>&1)"
if grep -q PATTERN <<< "${out}"; then …
```

### Learning 3 — `confirm default-no` under NONINTERACTIVE always refuses (round 51)

**Class:** scripts that gate state-mutating operations with
`confirm "…" default-no` work correctly interactively but ALWAYS refuse
under `SOVEREIGN_OS_NONINTERACTIVE=1`. The "no" is the sane default;
but tooling that wants to script the mutation needs a bypass.

**Fix pattern:** add a env-gate alongside `confirm`:
```bash
if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
  if ! confirm "…" default-no; then …
fi
```

### Learning 4 — SDD-stated invariants need CODE GUARDS, not just SDD comments (bug 15, round 108)

**Class:** SDD text said "X MUST NOT happen" but the code path didn't
enforce it — only the SDD comment did. SDD-023 § Meta-observability
EXPLICITLY warned the alerts rule engine "MUST NOT react to `sovereign_os_meta_*`
metrics — prevents self-reinforcing alert loops." The rule engine was
shipped without that guard. Bug latent in production until a Layer 2
schema test specifically asserted the invariant.

**Fix pattern:** every SDD-stated MUST/MUST-NOT invariant gets:
1. An explicit code guard (`if name.startswith("sovereign_os_meta_"): continue`)
2. A test that would fail if the guard is removed (the L2 schema test)

Catches: silent contract drift between SDDs (where invariants are
written) and code (where invariants must be enforced).

### Learning 5 — Singular-vs-plural in test grep patterns (round 106)

**Class:** L3 test grep `"files on disk differ"` failed against output
`"file(s) on disk differ"` — the production code parenthesizes for
"1 file vs N files" grammar. Test pattern didn't account for that.
The test failure made the new feature look broken when it wasn't.

**Fix pattern:** test patterns use regex with `file\(s\)` or `files?`
to match either form. More broadly: prefer regex over literal grep
when the production string might pluralize, capitalize, or punctuate
contextually.

## Cross-references

- SDD-008 § Layer 3 stage acceptance — where this discipline is specified
- `tests/nspawn/test_*.sh` — the ~55 L3 scripts implementing it
- `tests/unit/test_*_json_schema.py` — the L2 schema-pinning tests
  (SDD-023 alerts contract + SDD-025 audit drift contract)
- `docs/handoff/003-operator-observability-arc.md` — chronological
  trajectory + the ledger above is the running tally
