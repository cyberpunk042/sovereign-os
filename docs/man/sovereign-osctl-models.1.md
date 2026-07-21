% SOVEREIGN-OSCTL-MODELS(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-models - models, inference, and scientific compute

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Model discovery, placement, serving, routing, evaluation, adaptation, gateway behavior, and non-LLM scientific compute.

This page owns 19 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Model pulls consume storage; serving and evaluation consume VRAM and power. Prefer plan, info, list, status, suggest, and health verbs before start, run, remove, or adaptation actions.

Read-only discovery should precede mutation. JSON output, when offered,
is the stable surface for automation; human output is intended for direct
operator use.

# COMMON WORKFLOW

1. Confirm the installed revision with **sovereign-osctl version**.
2. Inspect the relevant **status**, **show**, **list**, **info**, **plan**,
   or **doctor** surface.
3. Save machine-readable output when `--json` is available.
4. Review profile, device, backend, policy, and target selection.
5. Apply the smallest scoped mutation, then re-run health/status.

# EXAMPLES

    sovereign-osctl models query --class reasoning --json
    sovereign-osctl models suggest --runtime-profile high-concurrency --json
    sovereign-osctl gateway --json
    sovereign-osctl model-serve list

# COMMAND REFERENCE

## models

The default resident-model directory is `/mnt/vault/models`; override it with `SOVEREIGN_OS_MODELS_DIR`.

**sovereign-osctl models docs [--check|--stdout]**
:   Regenerate docs/src/model-catalog.md (R206, SDD-028 pattern)

**sovereign-osctl models query [--class C] [--tier T] [--purpose P] [--size-class S] [--quantization Q] [--status S] [--max-vram N] [--min-context N] [--engine E] [--base-model B] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models suggest --runtime-profile <id> [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models suggest --list**
:   R214: profile-aware suggester — flags

**sovereign-osctl models select --class C[,C] --vram N [--tier T] [--purpose P] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models info <slug> [--json]**
:   R231 (SDD-026 Z-2): LM-Studio-equivalent

**sovereign-osctl models eval list-benchmarks [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models eval plan <slug> --benchmark B [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models eval run <slug> --benchmark B [--dry-run] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models eval history [--slug S] [--benchmark B] [--limit N] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models toolchains list [--kind K] [--installed-only] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models toolchains info <name> [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models fine-tune list-methods [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models fine-tune plan <base> --method M --dataset D [--output-dir D] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models fine-tune run <base> --method M --dataset D [--dry-run] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models fine-tune history [--base B] [--method M] [--limit N] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl models list**
:   List resident models (the model directory)

**sovereign-osctl models pull <hf-id>**
:   Pull model from HuggingFace into the model directory

**sovereign-osctl models verify**
:   Verify resident-model integrity

**sovereign-osctl models size**
:   Disk-usage breakdown of the model directory

**sovereign-osctl models remove <name>**
:   Delete a resident model (confirms)

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

## router

**sovereign-osctl router status**
:   R516 router surface (SDD-011) — service + listen check

**sovereign-osctl router classify <prompt>**
:   Show routing decision for a prompt (delegates to inference route)

**sovereign-osctl router plan <prompt> [--task-type T] [--think] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl router rules**
:   Print the 5 routing rules verbatim (SDD-011)

**sovereign-osctl router metrics**
:   R517 — routing decision counts from Layer B textfile

**sovereign-osctl router watch**
:   R516 refresh-loop TUI (router + 4 tiers at a glance)

## science

**sovereign-osctl science list [--json]**
:   R558 (SDD-070): science-tools catalog by domain

**sovereign-osctl science status [--json]**
:   NVIDIA Warp installed? + device (cuda:0 or CPU) + version

**sovereign-osctl science run [--device cpu|cuda] [--particles N] [--steps M] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl science info <id> [--json]**
:   Full detail for one science tool

**sovereign-osctl science install [--json]**
:   How each integrated tool is obtained (advisory)

## warp

**sovereign-osctl warp list|libs|relations|info <scene>|status [--json]**
:   SDD-300: Warp management — the warp-solar-system-shaders engine (scenes, libs, and the scene→lib / lib→lib relation graph) read from config/warp-catalog.yaml

**sovereign-osctl warp render <scene> [--json]**
:   Render a scene (GPU cuda:0 or CPU) — exec-rail-gated; needs a shaders checkout (WARP_SHADERS_ROOT) or prints an honest no-op

**sovereign-osctl warp bench <scene> [--json]**
:   Benchmark a scene (ms/frame) — exec-rail-gated

## chromofold

**sovereign-osctl chromofold info [--json]**
:   SDD-400: ChromoFold compressed-domain search — print the read-only capability descriptor (ABI version, library, headers, and the per-primitive map incl. the Lane-A fm_count) read from the native packaging/chromofold_capability.json in the resident engine checkout (CHROMOFOLD_ROOT, else WARP_SHADERS_ROOT). Reports the offline state honestly (exit 0) when none is resident.

**sovereign-osctl chromofold selftest [--json]**
:   The no-GPU header-seam self-test: validate the committed reference fixtures' 4-byte magic + u32-LE version against the engine's own capability descriptor (mirroring packaging/seam_check.c). Never touches a GPU or mutates state.

## gateway

**sovereign-osctl gateway [--addr host:port] [--json]**
:   See the handler for behavior and options.

## model-serve

**sovereign-osctl model-serve start <id> --model <path> --vram N [--engine llama-server|vllm] [--port P] [--dialect openai|anthropic] [--device auto|logic|oracle]**
:   Launch / stop / list a GPU serve-process model (SDD-902): the ergonomic front to the jobs-api model-serve job kind. start places a model on a GPU by free VRAM (the compute plane), launches llama-server / vLLM, and registers it as a gateway PROXY backend so /v1/messages + the OpenAI shim reach it; stop cancels (unregister + release VRAM); background designates the "background" alias.

**sovereign-osctl model-serve stop <id>**
:   Additional supported form.

**sovereign-osctl model-serve list**
:   Additional supported form.

**sovereign-osctl model-serve background [<id> | --clear]**
:   Additional supported form.

## wasm-aot

**sovereign-osctl wasm-aot status|compile-cmd <wasm>|advisory [--json]**
:   See the handler for behavior and options.

## zmm-ternary

**sovereign-osctl zmm-ternary status|perf-cmd|advisory [--json]**
:   See the handler for behavior and options.

## model-params

**sovereign-osctl model-params {list|show|recommend}**
:   R311 (E5.M7 closure): LLM-runtime parametrization advisor. Per-parameter catalog with hardware-aware recommended values (context_size / n_gpu_layers / cache_type_k+v / batch_size / parallel / mlock / mmap / flash_attn / rope_freq_base / temperature / top_p). Operator-named (§1b verbatim: "Model variants + quantizations + advanced features parametrization").

## model-adapt

**sovereign-osctl model-adapt {tasks|recipes|recommend|show}**
:   R350 (E5.M17): task → (base, method, target GPU) recommender. Operator-named §1b verbatim: "download, fine-tune, parameters, build, run, use and train and adapt and use and eval and etc." ADAPT sits upstream of R244 fine-tune + R232 eval; consults R317 catalog GPU VRAM via R348 inventory_consult helper.

## model-build

**sovereign-osctl model-build {recipes|plan|show|history}**
:   R353 (E5.M18): fills the "build" verb in the §1b 9-verb AI tools pipeline (download/fine-tune/parameters/BUILD/run/use/train/ adapt/eval). Plans merge/quantize/export of a deployable model artifact from {base + adapter + recipe}. Hardware-aware via the same declared-GPUs pattern as R350 adapt.

## lifecycle

**sovereign-osctl lifecycle [arguments]**
:   R290 (E5.M6): end-to-end fine-tune lifecycle — threads R244 fine-tune + R232 eval + R182 selfdef registry into ONE operator-pull workflow. Operator-named (§1b mandate): "End-to-end fine-tune lifecycle (operator triggers training → eval → register)". Read-only; emits the next pending command for the operator to run.

## workflow

**sovereign-osctl workflow [arguments]**
:   R291 (E5.M9): operator-mutable flexible profile — full 9-stage workflow (download / fine-tune / parameters / build / run / use / train / adapt / eval) the operator named in §1b verbatim. Sibling to lifecycle (R290 / E5.M6); covers the broader operator surface beyond the fine-tune-focused 5-stage subset.

## model-health

**sovereign-osctl model-health [arguments]**
:   M060 D-03 (R10069-R10074): unified model-health core — joins the model catalog (models/catalog.yaml) to the SRP hardware topology (M075 Conductor/Logic/Oracle), overlays live GPU telemetry (nvidia-smi) + optional inference-fabric runtime state (loaded models, KV cache, p50/p95/p99 latency). Read-only; the sovereign-model-health-api daemon serves the D-03 cockpit dashboard from this same core. Verbs: status / catalog / gpus (+ --json).

## costs

**sovereign-osctl costs [arguments]**
:   M060 D-04 (R10075-R10082): cost aggregation core — joins the operator cost policy (/etc/sovereign-os/cost-policy.toml, dump 9885-9930) to the per-span cost attribute of the M049 span log, aggregating daily / project / MS040-profile / model spend + 30-day trend + end-of-day forecast. Read-only; the sovereign-costs-api daemon serves the D-04 cockpit dashboard from this same core. Verbs: summary / policy / today / export {csv|json} (+ --json). Read-only — the WRITE side is cost-policy.

## cost-policy

**sovereign-osctl cost-policy [arguments]**
:   M060 D-04 write surface — flip cloud_enabled in /etc/sovereign-os/cost-policy.toml so the operator can HALT (or resume) all cloud spend from the cockpit. DRY-RUN by default; a real write needs --confirm (baked into the control-systems change_cli) AND, via the exec daemon, the operator key + type-to-confirm + SOVEREIGN_OS_ACTION_EXEC_LIVE. Verbs: show / halt-cloud / resume-cloud.

## adapters

**sovereign-osctl adapters {inventory|list|history|promote|demote|rollback|register|gate}**
:   M060 D-11 (R10109-R10111): LoRA adapter inventory + promotion status — joins the model catalog's class=lora-adapter entries (M046 LoRA Foundry) to the promotion registry (per-adapter status + MS041 triple-gate + eval gain + NVFP4 recipe (M077) + promotion/rollback history). Read-only; the sovereign-adapters-api daemon serves the D-11 cockpit dashboard from this same core. READ verbs (inventory / list / history) → adapter-foundry.py (never mutates). WRITE verbs (promote / demote / rollback / register, SDD-051) → adapter-decide.py: transition the promotion registry (MS041 triple-gate on promote) + record a durable, audited decision. Decisions are --confirm + operator-key + type-to-confirm gated (via the cockpit exec daemon) and DRY-RUN by default; MS003 signing is defe...

## evals

**sovereign-osctl evals [arguments]**
:   M060 D-10 (R10106-R10108): eval-history aggregation — reads the Eval-Value fabric's eval-run log, aggregates per-task pass/fail + per-model trend + benchmark-suite progress (M078 HölderPO + M080 HRM targets) + adapter-promotion candidates (from the D-11 adapter core). Enforces the M079 WB/BB disaggregation invariant (white-box benchmarks NEVER averaged with black-box). Read-only; the sovereign-evals-api daemon serves the D-10 cockpit dashboard from this same core. Verbs: summary / suites / candidates (+ --json, --window).

## super-model

**sovereign-osctl super-model [arguments]**
:   M060 D-19 (R10124-R10125): super-model manifest — sovereign-os-native version + module-version table computed LIVE from git HEAD + the milestone catalog (M001..M080 ids/titles/R-row counts) + config/super-model- manifest.toml editorial overlay (M053 11 build-phases + per-milestone family/status). Read-only; the sovereign-super-model-api daemon serves the D-19 cockpit dashboard from this same core. Verbs: snapshot / version / milestones (+ --json).

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
