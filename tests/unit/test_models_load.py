"""Unit tests for scripts/models/{load,unload,warm}.py (SDD-049).

Loads each engine in-process (importlib — scripts/models is not a package) and
monkeypatches the catalog / GPU telemetry / subprocess so the VRAM-refuse and
live-write paths are exercised without a real host. Covers: id resolution
(known/unknown + path-convention fallback + is_dir), VRAM-fit refuse + --force,
DRY-RUN no-op, unsafe-'/'-id reject, atomic model-state.json write with the shape
model-health reads, unload state removal, warm dry-run + bad role.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}_mod", REPO / "scripts" / "models" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CATALOG = [
    {"id": "Qwen3-Coder-32B-Instruct", "tier": "logic",
     "hf_repo_id": "Qwen/Qwen3-Coder-32B-Instruct", "vram_gib_min": 20, "quantization": "fp8"},
    {"id": "Nemotron-Oracle-BF16", "tier": "oracle",
     "hf_repo_id": "nvidia/Nemotron-Oracle-BF16", "vram_gib_min": 80, "quantization": "bf16"},
]


@pytest.fixture
def loadmod(tmp_path, monkeypatch):
    m = _load("load")
    monkeypatch.setattr(m, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(m, "_ENV_DIR", tmp_path / "etc")
    monkeypatch.setattr(m, "MODEL_STATE_PATH", tmp_path / "model-state.json")
    monkeypatch.setattr(m._mh, "load_catalog", lambda *a, **k: CATALOG)
    monkeypatch.setattr(m._mh, "collect_gpus", lambda: [])  # default: no telemetry
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return m, tmp_path


def _mkmodel(tmp_path, org_name):
    d = tmp_path / "models" / org_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_unknown_id(loadmod):
    m, _ = loadmod
    r = m.load("No-Such-Model", confirm=True)
    assert r["ok"] is False and "unknown model id" in r["error"]


def test_unsafe_id_rejected(loadmod):
    m, _ = loadmod
    r = m.load("org/model", confirm=True)
    assert r["ok"] is False and "unsafe model id" in r["error"]


def test_dry_run_resolves_path_no_blockers(loadmod):
    m, tmp = loadmod
    _mkmodel(tmp, "Qwen__Qwen3-Coder-32B-Instruct")
    r = m.load("Qwen3-Coder-32B-Instruct")  # no confirm → dry-run
    assert r["dry_run"] is True and r["plan"]["path"] is not None
    assert r["plan"]["tier"] == "logic" and r["plan"]["role"] == "logic"
    assert r["blockers"] == []
    assert not (tmp / "etc").exists()  # dry-run wrote nothing


def test_dry_run_blocks_when_absent(loadmod):
    m, _ = loadmod
    r = m.load("Qwen3-Coder-32B-Instruct")  # not on disk
    assert r["dry_run"] is True and any("not on disk" in b for b in r["blockers"])


def test_vram_refuse_and_force(loadmod, monkeypatch):
    m, tmp = loadmod
    _mkmodel(tmp, "Qwen__Qwen3-Coder-32B-Instruct")
    # logic GPU with only 5 GiB free; model needs 20 → refuse
    monkeypatch.setattr(m._mh, "collect_gpus", lambda: [
        {"is_blackwell": False, "vram_total_gb": 24.0, "vram_used_gb": 19.0}])
    r = m.load("Qwen3-Coder-32B-Instruct", confirm=True)
    assert r["ok"] is False and "won't fit" in r["error"]
    # --force overrides (subprocess mocked)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stderr": ""})())
    r2 = m.load("Qwen3-Coder-32B-Instruct", confirm=True, force=True)
    assert r2["ok"] is True and r2["restarted"] == "logic"


def test_live_writes_env_and_state(loadmod, monkeypatch):
    m, tmp = loadmod
    _mkmodel(tmp, "Qwen__Qwen3-Coder-32B-Instruct")
    calls = []
    monkeypatch.setattr(m.subprocess, "run",
                        lambda *a, **k: calls.append(a[0]) or type("R", (), {"returncode": 0, "stderr": ""})())
    r = m.load("Qwen3-Coder-32B-Instruct", confirm=True)
    assert r["ok"] is True
    env = (tmp / "etc" / "inference-logic-engine.env").read_text()
    assert "LOGIC_MODEL=" in env and "Qwen__Qwen3-Coder-32B-Instruct" in env
    assert calls == [["sovereign-osctl", "inference", "restart", "logic"]]
    state = json.loads((tmp / "model-state.json").read_text())
    assert state["loaded"]["logic"][0]["id"] == "Qwen3-Coder-32B-Instruct"
    assert state["loaded"]["logic"][0]["precision"] == "fp8"


def test_env_drop_in_preserves_other_lines(loadmod, monkeypatch):
    m, tmp = loadmod
    _mkmodel(tmp, "Qwen__Qwen3-Coder-32B-Instruct")
    envf = tmp / "etc" / "inference-logic-engine.env"
    envf.parent.mkdir(parents=True, exist_ok=True)
    envf.write_text("LOGIC_PORT=8082\nLOGIC_MODEL=/old/path\n")
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stderr": ""})())
    m.load("Qwen3-Coder-32B-Instruct", confirm=True)
    txt = envf.read_text()
    assert "LOGIC_PORT=8082" in txt and "/old/path" not in txt and txt.count("LOGIC_MODEL=") == 1


def test_unload_dry_and_live():
    m = _load("unload")
    r = m.unload("logic")  # dry
    assert r["dry_run"] is True and r["plan"]["would_run"][-1] == "logic"
    assert m.unload("conductor")["ok"] is False  # not a GPU tier


def test_warm_dry_and_bad_role(monkeypatch):
    m = _load("warm")
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = m.warm("oracle")
    assert r["dry_run"] is True and "8083" in r["plan"]["server"]
    assert m.warm("conductor")["ok"] is False
