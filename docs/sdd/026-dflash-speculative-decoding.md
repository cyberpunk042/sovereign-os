# SDD-026 — DFlash speculative decoding integration (Round 157)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Derived from: master spec Block 7 DFlash addition (verbatim operator
> text); arXiv:2602.06036 "DFlash: Block Diffusion for Flash
> Speculative Decoding" (Z-Lab, Feb 2026); github.com/z-lab/dflash
> (L0 cross-references verified at info-hub ingest 2026-05-15).

## Problem

The master spec Block 7 operator-added topic introduces DFlash with
the verbatim framing:

> "And there is also Dflash I recently learned about that somehow
> with code task on model that fit in memory like any functional
> model in general it can work 3 times faster, does not work on
> creative tasks in general but interesting topic and place of
> introspection and knowledge"

This carries TWO load-bearing operator constraints we must encode:

1. **DFlash's gain is task-type-conditional.** It accelerates code +
   math (matches the paper's reported pattern — highest gains on math
   /code, moderate on conversational). It does NOT work for creative
   tasks. Naively enabling it for all requests would degrade output
   quality on the very requests sovereign-os MUST serve cleanly
   (writing, ideation, identity-aligned responses).

2. **Operator-introspection-friendly.** Operator describes DFlash as
   "interesting topic and place of introspection and knowledge" —
   the integration must surface its decision (was DFlash used for
   this request? why?) so the operator can observe and reason about it
   without RTFM-ing the backend internals.

## Decision: gated wrapper + Layer B observability + opt-out knobs

### Gating policy (sacrosanct, encoded verbatim in operator_note)

| task_type      | default decision | rationale (operator verbatim)                          |
|----------------|------------------|--------------------------------------------------------|
| code           | enabled          | "3 times faster" on code tasks                         |
| math           | enabled          | matches paper's code+math acceleration pattern         |
| conversational | disabled         | moderate gains; not worth quantization noise           |
| creative       | disabled         | "does not work on creative tasks in general"           |

Operator overrides:
- `DFLASH_ENABLE_OVERRIDE=1` — force-enable for any task_type (e.g.
  the operator wants to benchmark DFlash on creative output to
  empirically confirm the paper's caveat)
- `DFLASH_DISABLE_OVERRIDE=1` — force-disable globally (e.g. DFlash
  install broken; operator wants to fall back to vanilla decoding
  without redeploying)

### Surface

`scripts/inference/dflash-wrap.sh` — argv-prefix wrapper:

```sh
dflash-wrap.sh --task-type {code|math|conversational|creative} \
               --backend {vllm|llama_cpp|transformers} \
               -- <backend argv ...>
```

Per-backend integration:
- **vllm**: appends `--speculative-config '{"method":"dflash","path":...}'`
- **llama_cpp**: appends `--draft-model ${DFLASH_PATH}/draft.gguf`
- **transformers**: exports `PYTHONPATH=${DFLASH_PATH}` so dflash
  generation strategy is importable

### Install path (operator-facing)

```sh
git clone https://github.com/z-lab/dflash /opt/dflash
cd /opt/dflash && pip install -e .
```

The wrapper detects absence of `${DFLASH_PATH}` and gracefully falls
back to vanilla decoding with a WARN log + `decision="disabled-no-install"`
metric label. Operator never gets a hard failure due to install
state — only a clearly-tagged downshift.

### Observability

Layer B metrics (consumed by `sovereign-osctl metrics show dflash`):

| metric                                          | type    | labels               |
|-------------------------------------------------|---------|----------------------|
| sovereign_os_dflash_decision_total              | counter | task_type, decision  |
| sovereign_os_dflash_last_invocation_timestamp   | gauge   | task_type            |

Layer A (JSONL): each wrapper run prints decision + reason to stdout
via log_info, which the inference-tier service captures into
journald → SDD-016 Layer A pipeline → `sovereign-osctl journal show inference`.

## Out of scope (this SDD)

- Benchmarking DFlash speedup empirically against the operator's
  actual code+math workload (Layer 5 hardware-required validation)
- Per-model speculative-decoding tuning (e.g. draft-model size,
  acceptance-rate target) — operator-tunable later
- The DFlash-via-router upstream path (router routes by task_type
  signal; that signal needs to be added to the router schema — see
  R157 follow-up)

## Master spec § citation discipline

The wrapper script header cites Block 7 verbatim; the gating
decision-reason strings preserve the operator's exact phrasing ("3×
faster" / "does not work on creative tasks in general") so that
operators reading runtime decisions see the source-of-truth wording.
