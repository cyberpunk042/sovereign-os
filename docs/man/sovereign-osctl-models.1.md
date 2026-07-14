% SOVEREIGN-OSCTL-MODELS(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-models - models, inference, and scientific compute

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Model discovery, placement, serving, routing, evaluation, adaptation, gateway behavior, and non-LLM scientific compute.

This page owns 17 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Model pulls consume storage; serving and evaluation consume VRAM and power. Prefer plan, info, list, status, suggest, and health verbs before start, run, remove, or adaptation actions.

Read-only discovery should precede mutation. JSON output, when offered,
is the stable surface for automation; human output is intended for direct
operator use.

# COMMON WORKFLOW

1. Inspect the relevant **status**, **show**, **list**, **info**, **plan**,
   or **doctor** surface.
2. Save machine-readable output when `--json` is available.
3. Review profile, device, backend, policy, and target selection.
4. Apply the smallest scoped mutation.
5. Re-run health/status and inspect alerts or journal output.

# EXAMPLES

    sovereign-osctl models query --class reasoning --json
    sovereign-osctl models suggest --runtime-profile high-concurrency --json
    sovereign-osctl gateway --json
    sovereign-osctl model-serve list

# COMMAND REFERENCE

## models

**sovereign-osctl models docs [--check|--stdout]**
:   Regenerate docs/src/model-catalog.md (R206, SDD-028 pattern)

**sovereign-osctl models query [--class C] [--tier T] [--purpose P] [--size-class S] [--quantization Q] [--status S] [--max-vram N] [--min-context N] [--engine E] [--base-model B] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models suggest --runtime-profile <id> [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models suggest --list**
:   R214: profile-aware suggester — flags

**sovereign-osctl models select --class C[,C] --vram N [--tier T] [--purpose P] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models info <slug> [--json]**
:   R231 (SDD-026 Z-2): LM-Studio-equivalent

**sovereign-osctl models eval list-benchmarks [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models eval plan <slug> --benchmark B [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models eval run <slug> --benchmark B [--dry-run] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models eval history [--slug S] [--benchmark B] [--limit N] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models toolchains list [--kind K] [--installed-only] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models toolchains info <name> [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models fine-tune list-methods [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models fine-tune plan <base> --method M --dataset D [--output-dir D] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models fine-tune run <base> --method M --dataset D [--dry-run] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models fine-tune history [--base B] [--method M] [--limit N] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl models list**
:   List resident models (tank/models)

**sovereign-osctl models pull <hf-id>**
:   Pull model from HuggingFace into tank/models

**sovereign-osctl models verify**
:   Verify resident-model integrity

**sovereign-osctl models size**
:   Disk-usage breakdown of tank/models

**sovereign-osctl models remove <name>**
:   Delete a resident model (confirms)

Run `sovereign-osctl help` for the complete version-matched grammar.

## inference

**sovereign-osctl inference status**
:   Per-tier backend status (Pulse / Logic / Oracle / Router)

**sovereign-osctl inference health**
:   HTTP-probe every tier's /healthz (with TCP fallback)

**sovereign-osctl inference start <tier>**
:   Start a tier (pulse | logic | oracle | router | all)

**sovereign-osctl inference stop <tier>**
:   Stop a tier

**sovereign-osctl inference restart <tier>**
:   Restart a tier

**sovereign-osctl inference route <prompt>**
:   Show which tier the router would pick for a sample request

**sovereign-osctl inference prompt <text>**
:   Run a single prompt through the router (streams tokens; SDD-062 M058)

**sovereign-osctl inference logs <tier>**
:   Tail systemd journal for the tier

Run `sovereign-osctl help` for the complete version-matched grammar.

## router

**sovereign-osctl router status**
:   R516 router surface (SDD-011) — service + listen check

**sovereign-osctl router classify <prompt>**
:   Show routing decision for a prompt (delegates to inference route)

**sovereign-osctl router plan <prompt> [--task-type T] [--think] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl router rules**
:   Print the 5 routing rules verbatim (SDD-011)

**sovereign-osctl router metrics**
:   R517 — routing decision counts from Layer B textfile

**sovereign-osctl router watch**
:   R516 refresh-loop TUI (router + 4 tiers at a glance)

Run `sovereign-osctl help` for the complete version-matched grammar.

## science

**sovereign-osctl science list [--json]**
:   R558 (SDD-070): science-tools catalog by domain

**sovereign-osctl science status [--json]**
:   NVIDIA Warp installed? + device (cuda:0 or CPU) + version

**sovereign-osctl science run [--device cpu|cuda] [--particles N] [--steps M] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl science info <id> [--json]**
:   Full detail for one science tool

**sovereign-osctl science install [--json]**
:   How each integrated tool is obtained (advisory)

Run `sovereign-osctl help` for the complete version-matched grammar.

## gateway

**sovereign-osctl gateway [--addr host:port] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## model-serve

**sovereign-osctl model-serve [arguments]**
:   The Sovereign Compute Plane (via jobs-api :8142) — the box's devices with LIVE free VRAM + the outstanding claims (model residents + running GPU jobs), placed by the M075 SRP doctrine. Read-only. A GPU job is placed on a device that fits, or waits, so it never OOMs the box. plane human summary

Run `sovereign-osctl help` for the complete version-matched grammar.

## wasm-aot

**sovereign-osctl wasm-aot status|compile-cmd <wasm>|advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## zmm-ternary

**sovereign-osctl zmm-ternary status|perf-cmd|advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## model-params

**sovereign-osctl model-params [arguments]**
:   R312 (E1.M32): operator's exact board ASUS ProArt X870E-CREATOR WIFI specific tuning advisor. PCIe slot allocation + M.2 speed matrix + dual-GPU bifurcation modes + BIOS-flashback recipe + memory training timeout + known issues. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## model-adapt

**sovereign-osctl model-adapt [arguments]**
:   R349 (E10.M1): AI-as-guide topic catalog — operator-pull "guide me into the kernel / hardware / gpu / psu / ups / memory / workload-mode / inference / network". Each topic carries layers + verbs + thresholds + BIOS/HW caveats. Operator-named (§1b verbatim: "only a guide into the experience, into the field, into the kernel, into the hardware, into the OS, into the modules…").

Run `sovereign-osctl help` for the complete version-matched grammar.

## model-build

**sovereign-osctl model-build [arguments]**
:   R351 (E2.M34): "what have I installed but not yet configured?" Operator-named §1b verbatim: "installs, non-configured, modules or features and how configure them". 16-module default catalog; per-module verdict (fully-configured / installed-not-configured / running-without-overlay / config-only-no-runtime / shipped-but- untouched) + the verb to close each gap.

Run `sovereign-osctl help` for the complete version-matched grammar.

## model-health

**sovereign-osctl model-health [arguments]**
:   M060 D-09 (R10102-R10105): unified hardware-pressure core — Linux PSI (/proc/pressure cpu/mem/io) + dual-CCD topology (M070) + GPU (nvidia-smi) + ZFS pool/dataset latency (M068) + scheduler backpressure (M058). Read -only; the sovereign-hardware-pressure-api daemon serves the D-09 cockpit dashboard from this same core. Verbs: status / psi / zfs (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## costs

**sovereign-osctl costs [arguments]**
:   M060 D-05 (R10083-R10087): M049 13-field span store + query core — reads the observability fabric's append-only span log (/var/log/sovereign-os/spans.jsonl), filters by time window / text / severity / OCSF class (MS026 16-event taxonomy), assembles per-trace span trees. Read-only; the sovereign-traces-api daemon serves the D-05 cockpit dashboard from this same core. Verbs: spans / trace <id> / summary (+ --json, --window, --q, --severity, --ocsf-class).

Run `sovereign-osctl help` for the complete version-matched grammar.

## cost-policy

**sovereign-osctl cost-policy [arguments]**
:   M060 D-04 (R10075-R10082): cost aggregation core — joins the operator cost policy (/etc/sovereign-os/cost-policy.toml, dump 9885-9930) to the per-span cost attribute of the M049 span log, aggregating daily / project / MS040-profile / model spend + 30-day trend + end-of-day forecast. Read-only; the sovereign-costs-api daemon serves the D-04 cockpit dashboard from this same core. Verbs: summary / policy / today / export {csv|json} (+ --json). Read-only — the WRITE side is cost-policy.

Run `sovereign-osctl help` for the complete version-matched grammar.

## adapters

**sovereign-osctl adapters [arguments]**
:   M060 D-04 write surface — flip cloud_enabled in /etc/sovereign-os/cost-policy.toml so the operator can HALT (or resume) all cloud spend from the cockpit. DRY-RUN by default; a real write needs --confirm (baked into the control-systems change_cli) AND, via the exec daemon, the operator key + type-to-confirm + SOVEREIGN_OS_ACTION_EXEC_LIVE. Verbs: show / halt-cloud / resume-cloud.

Run `sovereign-osctl help` for the complete version-matched grammar.

## evals

**sovereign-osctl evals [arguments]**
:   SDD-061 (M046): the GATE-PRODUCER — advance an adapter's MS041 gate from REAL evidence. adapters gate {human|snapshot|eval|oracle} <id> → adapter-gate.py: human = operator attestation (the sole cockpit control, adapter-gate-human); snapshot = a real ZFS rollback-point (SDD-050); eval = a real passing evals.jsonl record (D-10); oracle = an oracle-backend judge. SB-077: honest-defer (gate stays pending) when the evidence/backend is absent — never fabricates a pass. eval/snapshot/oracle are CLI-...

Run `sovereign-osctl help` for the complete version-matched grammar.

## super-model

**sovereign-osctl super-model [arguments]**
:   M060 chain health observability — proxies the selfdef daemon's GET /v1/m060/health endpoint reporting publish-freshness of all 10 mirror artifacts (offline/degraded/stale/online plus this script's own "unreachable" when the daemon is down). Used by the D-00 master-dashboard's chain-health banner, the MCP tool selfdef-m060-health, and ops/smoke scripts. Read-only. Verbs: probe / state (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

# FILES

**/etc/sovereign-os/**
:   Installed configuration and active selections.

**/var/lib/sovereign-os/**
:   Per-machine runtime state.

**~/.sovereign-os/**
:   Per-operator state and logs where supported.

# EXIT STATUS

Zero indicates success. Non-zero indicates invalid input, failed checks,
missing dependencies, refused gates, or operational failure. Audit and
coverage surfaces may use status 2 for findings.

# SEE ALSO

**sovereign-osctl**(1), **sovereign-osctl-models**(1),
**sovereign-osctl-agents**(1), **sovereign-osctl-hardware**(1),
**sovereign-osctl-security**(1), **sovereign-osctl-operations**(1),
**sovereign-osctl-governance**(1), **sovereign-osctl-install**(1)

# REPORTING BUGS

GitHub: <https://github.com/cyberpunk042/sovereign-os/issues>

# LICENSE

AGPL-3.0-or-later
