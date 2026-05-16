# Bugs caught by Layer 3 discipline

A running ledger of real wiring bugs caught by the 5-layer TDD pyramid
(SDD-008). Every entry is a bug that ALSO passed Layer 1 (schema/lint)
+ Layer 2 (unit) — only the substantive Layer 3 nspawn-style tests
surfaced them.

Operationally important: 60% of these bugs belong to ONE class
(shell-var-vs-exported-env propagation into Python subshells). The
class is documented as Project Learning 1.

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

## Cross-references

- SDD-008 § Layer 3 stage acceptance — where this discipline is specified
- `tests/nspawn/test_*.sh` — the 35+ scripts implementing it
- `docs/handoff/002-foundation-substantive-buildout.md` — chronological
  trajectory + the ledger above is the running tally
