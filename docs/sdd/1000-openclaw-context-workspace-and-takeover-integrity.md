# SDD-1000 — OpenClaw context, workspace, and takeover integrity

> Status: draft
> Owner: operator-directed 2026-09-11 (*"Lets do SDD in sovereign-os to solve all those things"*); agent-authored.
> Trigger: OpenClaw session `92de6d8d-8ab5-4774-ac15-ebe5b34a220c` and the SAIN-01 Qwythos profile incident.
> Builds on: SDD-103 (bounded chat), SDD-705 (OpenClaw runtime), SDD-903 (profile-driven inference), SDD-951 (durable memory), SDD-981 (session communication).
> Mandate module: **E12.M1000**.

## Mission

An agent session must not become unsafe, unactionable, or misleading merely
because it is long, tool-heavy, compacted, or resumed by another agent. The
runtime must prove five facts before it acts:

1. which workspace is authoritative;
2. which profile and model are actually serving;
3. whether the complete request fits the *resident* context window;
4. what durable, bounded evidence is carried forward after compaction; and
5. whether a takeover instruction is still compatible with current runtime
   truth and later operator direction.

This prevents the observed failure sequence: a shadow workspace was edited,
large raw tool reads consumed the context, compaction retained too little useful
state, a stale provider list was treated as hardware truth, and a fresh
OpenClaw session overflowed because its bootstrap/tool payload alone exceeded
the worker's configured context.

## Invariants

### I1 — one authoritative workspace, never a guessed mirror

Every sovereign-os agent run carries a `workspace_identity` record:

```json
{
  "repo_root": "/home/jfortin/sovereign-os",
  "git_toplevel": "/home/jfortin/sovereign-os",
  "origin": "local-checkout",
  "write_root": "/home/jfortin/sovereign-os"
}
```

Before any write, the integration resolves the requested path against
`write_root`, verifies it remains below the git top-level, and records the
resolved path plus pre-write digest. `~/.openclaw/workspace` is an agent
scratch/workspace, **not** a sovereign-os mirror; a matching relative path
there must be rejected with an explicit `shadow-workspace` diagnostic unless
the operator selected it as the project root.

No write may create or truncate a profile under a non-authoritative root.
The real repository is never inferred from a file name alone.

### I2 — profile truth is a three-way attestation

The active profile is not a label. A profile is `serving` only when one
attestation binds all of the following:

| Fact | Authoritative witness |
|---|---|
| selected profile | `/etc/sovereign-os/active-runtime-profile` after reconcile commit |
| resident model / context / endpoint | each backend's `/health`, `/v1/models`, and `/props` |
| consumer catalog | OpenClaw provider entry plus its running gateway config revision |

The reconciler must publish this attestation atomically after health checks and
before advertising the profile. A consumer can show a model only when its id,
endpoint, card label, served alias, context limit, and active profile agree.
An obsolete entry is withdrawn, never merely overwritten with a new label.

### I3 — context admission uses the resident limit, not model marketing

The model catalog's maximum context is a capability ceiling. It is never a
request admission limit. For each provider request, the adapter computes:

```
resident_context = backend /props n_ctx (or declared reconciled launch context)
reserved_output  = profile max_output_tokens
fixed_context    = rendered system + workspace + tool schema + retrieval bytes
history_context  = rendered durable summary + selected transcript turns
request_context  = fixed_context + history_context + new user turn
```

Admission succeeds only when `request_context + reserved_output <=
resident_context - safety_margin`. The tokenizer used by the serving backend is
preferred; a conservative character estimate is allowed only as a preflight and
must be marked estimated. The OpenClaw catalog publishes the *same* resident
context and output cap.

If a fresh session fails admission, the runtime reports a breakdown by class
(system/workspace/tools/retrieval/history/output), not the misleading advice to
start another empty session. The selector must choose a compatible resident
model or reduce optional bootstrap material before dispatching. It must not
send a request it has already proved cannot fit.

### I4 — tool evidence is referenced, not replayed wholesale

Tool output has two representations:

- an immutable full artifact, addressed by digest and access-controlled at its
  source; and
- a bounded context projection containing command identity, exit status,
  timestamp, digest, size, key assertions, and a short excerpt.

The projection has a strict per-result and per-turn budget. Large reads,
database dumps, logs, and generated files are replaced by source references and
structured findings. The agent may fetch a targeted range from the original
artifact when needed; it must not re-inject every previous raw result after
compaction.

### I5 — compaction creates a takeover capsule

Every compaction produces a durable `takeover_capsule`, not prose alone:

```json
{
  "objective": "operator-verbatim reference",
  "workspace_identity": "digest",
  "profile_attestation": "digest",
  "decisions": [{"statement": "verbatim ref", "status": "active|superseded"}],
  "completed": [{"claim": "...", "evidence": "artifact digest"}],
  "open_actions": [{"action": "...", "authority": "...", "blocked_by": null}],
  "risks": ["..."],
  "raw_artifacts": ["digest refs"]
}
```

The capsule is bounded, machine-readable, and includes a compaction quality
metric: retained active decisions, evidence references, open actions, and
workspace/profile attestation must all be present. `nothing compactable` is a
failure when raw tool content dominates context; the runtime must project that
content before retrying compaction.

On takeover, an agent reads the capsule and re-attests the workspace and
runtime. A prior instruction that conflicts with a newer operator decision or
current serving state is marked `superseded`; it is never executed silently.
Destructive changes, including reallocating a GPU, still require an explicit
current operator decision.

## SAIN-01 policy derived from the incident

The RTX 4090 is neither "idle" nor permanently dedicated by a stale OpenClaw
picker. Its allocation is determined only by the active profile attestation.
The current Qwythos three-card profile declares it as a Qwythos worker. A future
two-card / memory-provider design must be a distinct profile with its own model,
memory service endpoint, VRAM budget, OpenClaw catalog behavior, migration
steps, and rollback path. It must not mutate `qwythos-three-card` in place.

For the present Qwythos worker, the reconciled 32,768-token resident context and
4,096-token output reserve are the consumer contract; the 1M catalog capability
is not advertised as live capacity.

## Required implementation slices

1. **Workspace resolver.** Add a sovereign-os-owned project descriptor and
   OpenClaw integration adapter that rejects shadow-root writes and records
   workspace identity with each run.
2. **Runtime attestation endpoint.** Extend the profile state publisher with
   per-provider served id, endpoint, card, resident context, output reserve,
   profile revision, and consumer-config revision. D-21 exposes it read-only.
3. **Context admission adapter.** Before OpenClaw dispatch, obtain the active
   provider's resident context, measure every context class, select a compatible
   provider or trim optional bootstrap projections, and emit an actionable
   refusal without contacting an impossible backend.
4. **Bounded evidence store.** Route large OpenClaw tool results through digest
   artifacts plus structured projections; add retrieval-by-reference for a
   requested artifact/range.
5. **Compaction and takeover capsule.** Store and validate the capsule, surface
   a takeover preview in D-21, and require current-state re-attestation before
   an agent continues a paused task.
6. **Profile transition discipline.** Model the two-card/memory-provider plan
   as a new profile. The existing three-card profile remains independently
   selectable and reversible.

## Acceptance contract

| Scenario | Required result |
|---|---|
| Agent attempts `~/.openclaw/workspace/...` write for a sovereign-os project | rejected as a shadow workspace; real root identified |
| Fresh OpenClaw request has bootstrap larger than selected resident context | preflight reports size breakdown and selects/fails before backend dispatch |
| Qwythos worker is launched at 32K | OpenClaw advertises 32K/4K, endpoint reports 32K, attestation is consistent |
| 16 KB tool read in a long task | full artifact retained once; next context contains a bounded projection/reference |
| Compaction after tool-heavy work | valid capsule has current objective, evidence digests, open actions, and active decisions |
| Takeover after profile change | stale instruction is flagged; no profile/GPU mutation occurs without current operator direction |
| A two-card design is selected | creates a distinct profile and preserves `qwythos-three-card` rollback |

## Non-goals

- Rewriting OpenClaw upstream or storing secret-bearing tool output in the
  sovereign-os repository.
- Treating compaction as permission to discard operator words or audit evidence.
- Automatically repurposing the RTX 4090 based on a session summary.
- Raising model context solely because a catalog advertises a large theoretical
  limit; every increase remains profile-declared and benchmark-gated.

## Verification

The implementation must add hermetic tests for workspace root rejection,
attestation agreement, fresh-session admission, context-class accounting,
tool-result projection bounds, capsule schema/quality, takeover conflict
detection, and profile coexistence/rollback. A live SAIN-01 smoke test records
the backend-reported context, OpenClaw effective model limits, and a successful
fresh OpenClaw request without an overflow retry.

## Cross-references

- `scripts/inference/sync-openclaw-models.py` — consumer limits derived from
  actual profile launch budgets
- `scripts/inference/reconcile-qwythos-three-card.py` — atomic runtime/profile
  convergence
- `scripts/iac/assets/publish-model-state.py` — current state publication
- `crates/sovereign-gatewayd/` — provider routing and request admission boundary
- SDD-103, SDD-705, SDD-903, SDD-951, SDD-981
