# SDD-151 — model-state publisher resolves the vault catalog dir, not an HF quant subfolder (D-21 showed `IQ3_S`)

> Status: complete — shipped + verified on branch (live-patched on this host)
> Owner: operator-reported; agent-authored
> Last updated: 2026-10-07
> Closes findings: operator report 2026-10-07 — *"weird behavior: oracle GPU0 · idle IQ3_S profile expects: Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S — it put IQ3_S but clearly i should have been Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S, right? In the same cockpit"*. Yes — the deployment deck / activation tracker (SDD-150 stage ③) render the RESIDENT id from `model-state.json`, and the publisher published the quant subfolder name as the model. Recover band (SDD-151 / E11.M151 per SDD-100).
> Derived from / extends: the SDD-1000-line runtime-attestation publisher (`scripts/iac/assets/publish-model-state.py`, "WHY IT REPORTS CATALOG IDS"), the model vault convention `<SOVEREIGN_OS_MODELS_DIR>/<catalog-id>/…` (pull.sh / lm-orchestration / `sovereign-osctl models`), and SDD-150's declared-vs-resident evidence chain.

## Problem

For sharded Hugging Face repos that carry a **quant subfolder** in the repo tree, the vault preserves that layout:

```
/mnt/vault/models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
```

`publish-model-state.py`'s process-detection fallback (`llama-server -m <path>` → **immediate parent dir = catalog id**) returned `IQ3_S` — the HF quant folder, not the model. The tier's `/v1/models` answer is the routing alias (`gpu-oracle`, matched by no catalog id), and the IaC-configured fallback id (`gpt-oss-120b`) is stale after a profile switch — so the panel honestly rendered the wrong id it was fed: an `IQ3_S` row + a "profile expects Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S" mismatch badge for a model that was in fact correctly resident.

A second, compounding fact discovered live: the deployed unit runs `SOVEREIGN_OS_ROOT=/opt/sovereign-os`, and that older tree's `models/catalog.yaml` (80 rows) **predates** the Flash-Next model — so even an index-only ancestor walk would miss the id. The fix must not depend on the deployed catalog being current.

## Fix

`scripts/iac/assets/publish-model-state.py`:

1. `_detect_model_from_process` → `_model_path_from_process`: returns the `-m` path **verbatim** (no id inference at scan time).
2. NEW `_catalog_id_from_model_path(path, index)`: walks ancestor dirs deepest-first taking the FIRST that names a catalogued model; on index miss, the **first level under the vault** (`VAULT_MODELS_DIR = $SOVEREIGN_OS_MODELS_DIR`, default `/mnt/vault/models` — the same convention as pull.sh/lm-orchestration/osctl) is the catalog dir; only then falls back to the immediate parent name (honest bare row for genuinely non-catalogued models).
3. `_effective_tiers` worker fallback uses the same resolver instead of `.parent.name`.

Deployed on this host by the module-86 install path (the `/usr/local/lib/sovereign-os/publish-model-state.py` copy — it matched the pre-fix repo byte-for-byte). The `sovereign-model-state.timer` (60 s) republished within one cycle.

## Doctrine

- The panel never guessed: every value it showed came from the publisher; the publisher's *inference rule* was wrong, not the display. Fixed at the observer, not the renderer.
- "Applying a profile is not evidence its models became resident" (deployment deck) stays intact — the same chain now names the resident model correctly, so SDD-150's stage ③ `live` verdict stops falsely reading `loading` after every Flash-Next switch.
- No new controls, endpoints, or privileges; publisher stays stdlib-only and read-modify-write (prompt.py's measured `tokens_per_sec` untouched).

## Verification

- `tests/unit/test_runtime_attestation.py` — 7 passed, incl. two new tests: nested-quant-subdir resolves to the catalog id (with catalog index AND with a STALE/empty index — the exact live /opt condition), and the flat layout + non-vault unknown-model honest fallback.
- Live: manual publisher run → `oracle=['Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S']`; after the 60 s timer, `GET :8129/api/lm-orchestration/grid` reports GPU0 oracle → `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S` (deck badge flips from mismatch to match).
- ruff (CI codes) clean on both touched files.

## Follow-up (not in scope)

`/opt/sovereign-os` is a stale deployed tree (catalog 80 rows vs 245-file repo's current one) while interactive rails run from the home checkout — two catalog readers, two freshness rules. The publisher now survives it; the drift itself (install-syncing /opt, or pointing the unit at the checkout it ships from) is an install-pipeline decision for the operator.
