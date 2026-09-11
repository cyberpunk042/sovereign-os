#!/usr/bin/env python3
"""Publish what the inference tiers are ACTUALLY serving to model-state.json.

WHY THIS EXISTS
    Every device cell in D-21 / D-22 / D-03 listed catalog CANDIDATES, not
    residents. The box showed GPU0 hosting DeepSeek-R1-Distill-70B while
    gpt-oss-120b was the process actually running, GPU1 hosting
    Qwen-32B-Ternary-Quant while Nemotron-30B served, and the eGPU hosting
    nomic-embed-text-v2-moe — a model not even downloaded — while bge-m3
    answered every request.

    Nothing was lying: model-health falls back to the catalog and labels it
    `model_source: catalog`. But a panel whose model rows describe an intention
    rather than a machine is the same failure that produced "EXT_GPU · N/A" and
    the silently-unrouted GPUs — it reports the plan and calls it the state.

    model-health already prefers `loaded` from /run/sovereign-os/model-state.json
    when it is present. The writers exist too (scripts/models/load.py publishes
    `loaded`, scripts/inference/prompt.py publishes measured `tokens_per_sec`).
    They had simply never run for the vLLM tiers, which systemd starts directly.
    So the data path was complete except for the part that observes reality.

WHAT IT DOES
    Asks each configured tier what IT says it is serving (`GET /v1/models` — the
    tier's own answer, not an inference from unit state), and writes the union to
    `loaded[role]`. A tier that does not answer contributes nothing, so a stopped
    tier DISAPPEARS from the panel rather than lingering as a claim.

    `tokens_per_sec` and every other key are preserved: prompt.py owns those, and
    this must not stamp on real measured telemetry.

WHY IT REPORTS CATALOG IDS
    A tier serves under its PROXY id (`gpu-embed`), because gatewayd's relay
    forwards the client's model field verbatim and the two must match. That id is
    a routing name; `BAAI-bge-m3` is the model. The config carries both, so the
    panel can show the model while the plumbing keeps its own names — and the
    catalog row comes along with it, so precision/status/context-window columns
    fill in exactly as they do today.

    The served id is recorded as `served_as`, so the routing name is not lost.

Config: /etc/sovereign-os/model-state-publish.env (written by scripts/iac
module 86), MODEL_STATE_TIERS as comma-separated `role@host:port@catalog-id`.

stdlib only. Exit 0 whenever it published something coherent — a down tier is a
normal state, not a failure.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# A development-linked unit may retain the old /opt location in its environment
# while executing this checkout. Prefer that configured root only when it is a
# complete sovereign-os source tree; otherwise the code's own checkout is the
# authoritative source. This removes a subtle dev→prod split where live state
# could observe current servers but be unable to hash the current profile.
_SOURCE_ROOT = Path(__file__).resolve().parents[3]
_configured_root = Path(os.environ.get("SOVEREIGN_OS_ROOT", "/opt/sovereign-os"))
_REPO_ROOT = (_configured_root if ((_configured_root / "scripts" / "inference" / "model-health.py").is_file()
                                    and (_configured_root / "profiles").is_dir())
              else _SOURCE_ROOT)
STATE_PATH = Path(
    os.environ.get("SOVEREIGN_OS_MODEL_STATE", "/run/sovereign-os/model-state.json")
)
TIERS = os.environ.get("MODEL_STATE_TIERS", "")
TIMEOUT = float(os.environ.get("MODEL_STATE_TIMEOUT", "3"))
PROFILE_MARKER = Path(os.environ.get(
    "SOVEREIGN_OS_ACTIVE_PROFILE", "/etc/sovereign-os/active-runtime-profile"
))
PROFILE_RUNTIME_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_PROFILE_RUNTIME_DIR", "/etc/sovereign-os/profile-runtime"
))
OPENCLAW_CATALOG_REVISION = Path(os.environ.get(
    "SOVEREIGN_OS_OPENCLAW_CATALOG_REVISION",
    "/etc/sovereign-os/openclaw-catalog-revision.json",
))


def _load_model_health() -> Any | None:
    """model-health owns the catalog parser; importing it keeps ONE reader of
    models/catalog.yaml rather than a second, drifting copy here."""
    path = _REPO_ROOT / "scripts" / "inference" / "model-health.py"
    try:
        spec = importlib.util.spec_from_file_location("_mh_for_publish", path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception as e:  # noqa: BLE001 — degrade to bare ids, never fail
        print(f"[warn] catalog unavailable ({e}); publishing ids without enrichment",
              file=sys.stderr)
        return None


def _catalog_index(mh: Any | None) -> dict[str, dict[str, Any]]:
    """catalog id → the same row shape the panels already render."""
    if mh is None:
        return {}
    try:
        return {
            row["id"]: row
            for rows in mh.catalog_by_role().values()
            for row in rows
            if row.get("id")
        }
    except Exception as e:  # noqa: BLE001
        print(f"[warn] catalog index failed ({e})", file=sys.stderr)
        return {}


def _json_endpoint(endpoint: str, path: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(
            f"http://{endpoint}{path}", timeout=TIMEOUT
        ) as r:
            if r.status != 200:
                return None
            doc = json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _as_positive_int(value: Any) -> int | None:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resident_context(model: dict[str, Any], props: dict[str, Any] | None) -> int | None:
    """Extract an actual backend limit, never a catalog marketing maximum."""
    meta = model.get("meta")
    candidates = [
        model.get("max_model_len"), model.get("n_ctx"),
        meta.get("n_ctx") if isinstance(meta, dict) else None,
    ]
    if isinstance(props, dict):
        generation = props.get("default_generation_settings")
        candidates.extend([
            props.get("n_ctx"),
            generation.get("n_ctx") if isinstance(generation, dict) else None,
        ])
    for candidate in candidates:
        parsed = _as_positive_int(candidate)
        if parsed:
            return parsed
    return None


def _probe_tier(endpoint: str) -> dict[str, Any]:
    """The backend is the witness for aliases and resident context."""
    doc = _json_endpoint(endpoint, "/v1/models")
    data = doc.get("data") if doc else None
    if not isinstance(data, list):
        return {"endpoint": endpoint, "reachable": False, "models": []}
    props: dict[str, Any] | None = None
    models = [model for model in data if isinstance(model, dict) and model.get("id")]
    if any(_resident_context(model, None) is None for model in models):
        props = _json_endpoint(endpoint, "/props")
    return {
        "endpoint": endpoint,
        "reachable": True,
        "models": [{
            "id": str(model["id"]),
            "resident_context_tokens": _resident_context(model, props),
        } for model in models],
    }


def _served_ids(endpoint: str) -> list[str]:
    """Compatibility helper for callers that need ids only."""
    return [model["id"] for model in _probe_tier(endpoint)["models"]]


def _active_profile_id() -> str | None:
    try:
        value = PROFILE_MARKER.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _profile_revision(profile_id: str | None) -> str | None:
    if not profile_id:
        return None
    # /opt may be a partial legacy deployment even when this live-linked source
    # checkout is current. A profile revision must be resolved from the tree
    # that actually contains the active profile, never silently omitted.
    for root in (_REPO_ROOT, _SOURCE_ROOT):
        for directory in ("profiles/runtime", "profiles/orchestration"):
            candidate = root / directory / f"{profile_id}.yaml"
            try:
                import hashlib
                return hashlib.sha256(candidate.read_bytes()).hexdigest()
            except OSError:
                continue
    return None


def _runtime_records() -> dict[str, dict[str, Any]]:
    """Read root-owned launch declarations emitted by the Qwythos reconciler."""
    result: dict[str, dict[str, Any]] = {}
    for role in ("logic", "oracle", "worker"):
        try:
            record = json.loads((PROFILE_RUNTIME_DIR / f"{role}.json").read_text())
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            result[role] = record
    return result


def _catalog_revision() -> dict[str, Any] | None:
    try:
        document = json.loads(OPENCLAW_CATALOG_REVISION.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def _effective_tiers(tiers: str, profile_id: str | None,
                     runtime: dict[str, dict[str, Any]]) -> str:
    """Add the profile-owned third card without changing IAC's base env file."""
    records = [record.strip() for record in tiers.split(",") if record.strip()]
    if profile_id != "qwythos-three-card":
        return ",".join(records)
    # The Qwythos profile replaces the normal embedding/reranker pair on the
    # 4090. Do not mark those intentionally stopped endpoints as profile
    # failures merely because IAC's generic publisher environment still lists
    # them.
    records = [record for record in records if not record.startswith("router@")]
    worker = runtime.get("worker") or {}
    try:
        endpoint = f"127.0.0.1:{int(worker['port'])}"
        catalog_id = str(worker.get("catalog_id") or Path(str(worker["model_path"])).parent.name)
    except (KeyError, TypeError, ValueError):
        return ",".join(records)
    if not any(record.split("@", 2)[1:2] == [endpoint] for record in records):
        records.append(f"router@{endpoint}@{catalog_id}")
    return ",".join(records)


def _read_state() -> dict[str, Any]:
    try:
        doc = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ms-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def collect(tiers: str, index: dict[str, dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Return panel rows plus direct, backend-originated observation records."""
    loaded: dict[str, list[dict[str, Any]]] = {}
    observations: list[dict[str, Any]] = []
    for record in (r.strip() for r in tiers.split(",")):
        if not record:
            continue
        parts = record.split("@")
        if len(parts) != 3:
            print(f"[warn] malformed tier record {record!r} (want role@host:port@catalog-id)",
                  file=sys.stderr)
            continue
        role, endpoint, catalog_id = (p.strip() for p in parts)
        probe = _probe_tier(endpoint)
        observations.append({"role": role, "catalog_id": catalog_id, **probe})
        served = probe["models"]
        if not served:
            continue
        # The configured catalog id is a fallback, not authority.  llama.cpp
        # reports an absolute GGUF path, while vLLM normally reports its proxy
        # id.  Prefer a catalog id recognisable in the server's own response so
        # a successful profile switch cannot leave D-21 showing the prior
        # resident model for another minute (or indefinitely after a reboot).
        served_id = served[0]["id"]
        # A base-model id can be a prefix of its GGUF variant; choose the most
        # specific matching catalog id so the panel retains the selected
        # Qwythos-…-GGUF identity rather than collapsing it to the BF16 parent.
        actual_id = next((mid for mid in sorted(index, key=len, reverse=True)
                          if mid in served_id), catalog_id)
        # The catalog row when the id is known, else a bare entry — a model that
        # is genuinely serving should appear even if it is not catalogued.
        row = dict(index.get(actual_id) or {"id": actual_id, "precision": None})
        row["served_as"] = served_id
        row["endpoint"] = endpoint
        row["resident_context_tokens"] = served[0]["resident_context_tokens"]
        loaded.setdefault(role, []).append(row)
    return loaded, observations


def _attestation(profile_id: str | None, observations: list[dict[str, Any]],
                 runtime: dict[str, dict[str, Any]], consumer: dict[str, Any] | None) -> dict[str, Any]:
    """Bind selected profile, resident backend facts, and consumer projection."""
    violations: list[str] = []
    expected_revision = _profile_revision(profile_id)
    providers: list[dict[str, Any]] = []
    consumer_models = {
        row.get("id"): row for row in (consumer or {}).get("models", [])
        if isinstance(row, dict) and row.get("id")
    }
    if consumer is None:
        violations.append("openclaw-catalog-revision-unavailable")
    elif consumer.get("profile_id") != profile_id:
        violations.append("openclaw-catalog-profile-mismatch")
    elif expected_revision and consumer.get("profile_revision_sha256") != expected_revision:
        violations.append("openclaw-catalog-profile-revision-mismatch")

    for observation in observations:
        role = observation["role"]
        worker = runtime.get("worker") or {}
        worker_endpoint = f"127.0.0.1:{worker.get('port')}" if worker.get("port") else None
        runtime_role = "worker" if role == "router" and observation["endpoint"] == worker_endpoint else role
        expected = runtime.get(runtime_role)
        models = observation.get("models") or []
        actual = models[0] if models else None
        provider = {
            "role": role,
            "endpoint": observation["endpoint"],
            "catalog_id": observation["catalog_id"],
            "reachable": bool(observation["reachable"]),
            "served_as": actual.get("id") if actual else None,
            "resident_context_tokens": actual.get("resident_context_tokens") if actual else None,
            "expected": expected,
        }
        if not observation["reachable"]:
            violations.append(f"{role}:backend-unreachable")
        if expected:
            expected_alias = expected.get("served_model_name")
            expected_context = _as_positive_int(expected.get("context_tokens"))
            expected_port = _as_positive_int(expected.get("port"))
            if expected_port and observation["endpoint"] != f"127.0.0.1:{expected_port}":
                violations.append(f"{role}:endpoint-mismatch")
            if actual and expected_alias and actual.get("id") != expected_alias:
                violations.append(f"{role}:served-alias-mismatch")
            if actual and expected_context and actual.get("resident_context_tokens") != expected_context:
                violations.append(f"{role}:resident-context-mismatch")
            catalog = consumer_models.get(expected_alias)
            if consumer is not None and catalog is None:
                violations.append(f"{role}:openclaw-model-missing")
            elif catalog is not None and expected_context and _as_positive_int(catalog.get("context_window_tokens")) != expected_context:
                violations.append(f"{role}:openclaw-context-mismatch")
            elif catalog is not None and expected_context and (_as_positive_int(catalog.get("max_output_tokens")) or 0) > expected_context:
                violations.append(f"{role}:openclaw-output-exceeds-context")
        providers.append(provider)
    return {
        "profile_id": profile_id,
        "profile_revision_sha256": expected_revision,
        "consumer_revision_sha256": (consumer or {}).get("consumer_revision_sha256"),
        "providers": providers,
        "consistent": not violations,
        "violations": violations,
        "observed_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def main() -> int:
    if not TIERS.strip():
        print("[warn] MODEL_STATE_TIERS is empty — nothing to publish", file=sys.stderr)
        return 0
    profile_id = _active_profile_id()
    runtime = _runtime_records()
    mh = _load_model_health()
    loaded, observations = collect(
        _effective_tiers(TIERS, profile_id, runtime), _catalog_index(mh)
    )

    state = _read_state()
    # Read-modify-write. tokens_per_sec is prompt.py's REAL measured telemetry and
    # must survive: this process knows what is resident, not how fast it runs.
    state["loaded"] = loaded
    state["runtime_attestation"] = _attestation(
        profile_id, observations, runtime, _catalog_revision()
    )
    state["updated_ts"] = datetime.now(tz=timezone.utc).isoformat()
    try:
        _atomic_write(STATE_PATH, state)
    except OSError as e:
        print(f"[error] cannot write {STATE_PATH}: {e}", file=sys.stderr)
        return 1
    total = sum(len(v) for v in loaded.values())
    detail = ", ".join(
        f"{role}={[m.get('id') for m in models]}" for role, models in sorted(loaded.items())
    ) or "nothing serving"
    print(f"published {total} loaded model(s): {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
