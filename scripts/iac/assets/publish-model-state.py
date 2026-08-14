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

_REPO_ROOT = Path(os.environ.get("SOVEREIGN_OS_ROOT", "/opt/sovereign-os"))
STATE_PATH = Path(
    os.environ.get("SOVEREIGN_OS_MODEL_STATE", "/run/sovereign-os/model-state.json")
)
TIERS = os.environ.get("MODEL_STATE_TIERS", "")
TIMEOUT = float(os.environ.get("MODEL_STATE_TIMEOUT", "3"))


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


def _served_ids(endpoint: str) -> list[str]:
    """What the tier says it serves. Empty when it does not answer — which is a
    normal state (loading, stopped, never provisioned), not an error."""
    try:
        with urllib.request.urlopen(
            f"http://{endpoint}/v1/models", timeout=TIMEOUT
        ) as r:
            if r.status != 200:
                return []
            doc = json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return []
    data = doc.get("data")
    if not isinstance(data, list):
        return []
    return [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]


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


def collect(tiers: str, index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """role → [catalog row + served_as/endpoint], for tiers that answered."""
    loaded: dict[str, list[dict[str, Any]]] = {}
    for record in (r.strip() for r in tiers.split(",")):
        if not record:
            continue
        parts = record.split("@")
        if len(parts) != 3:
            print(f"[warn] malformed tier record {record!r} (want role@host:port@catalog-id)",
                  file=sys.stderr)
            continue
        role, endpoint, catalog_id = (p.strip() for p in parts)
        served = _served_ids(endpoint)
        if not served:
            continue
        # The catalog row when the id is known, else a bare entry — a model that
        # is genuinely serving should appear even if it is not catalogued.
        row = dict(index.get(catalog_id) or {"id": catalog_id, "precision": None})
        row["served_as"] = served[0]
        row["endpoint"] = endpoint
        loaded.setdefault(role, []).append(row)
    return loaded


def main() -> int:
    if not TIERS.strip():
        print("[warn] MODEL_STATE_TIERS is empty — nothing to publish", file=sys.stderr)
        return 0
    mh = _load_model_health()
    loaded = collect(TIERS, _catalog_index(mh))

    state = _read_state()
    # Read-modify-write. tokens_per_sec is prompt.py's REAL measured telemetry and
    # must survive: this process knows what is resident, not how fast it runs.
    state["loaded"] = loaded
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
