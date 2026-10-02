"""SDD-301 — Science panel: live instrument (backend half).

Covers:
- the run-history store (write / bound / read / stats / best-effort failure)
  in scripts/science/warp-runner.py,
- the `science.py run` argument fix (the documented --device/--particles/
  --steps syntax must parse; flags forward to the runner only when set),
- `science.py history` delegation to the runner (single source for the store),
- per-tool live detection (import / hf / checkout + honest unknown),
- the science-api gpu context (nvidia-smi truth + honest degradation).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCIENCE = REPO_ROOT / "scripts" / "science" / "science.py"
RUNNER = REPO_ROOT / "scripts" / "science" / "warp-runner.py"
API = REPO_ROOT / "scripts" / "operator" / "science-api.py"
PY = sys.executable


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RUN = _load("warp_runner_sdd301", RUNNER)
SCI = _load("science_sdd301", SCIENCE)
API_MOD = _load("science_api_sdd301", API)


# ── run-history store ────────────────────────────────────────────────────────

def test_record_run_appends_jsonl(tmp_path, monkeypatch):
    store = tmp_path / "runs.jsonl"
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(store))
    RUN.record_run({"device": "cuda:0", "version": "1.15.0",
                    "sim": {"num_particles": 1000, "steps": 10, "dt": 0.01,
                            "wall_ms": 1.5, "mean_final_height": 0.5,
                            "settled": 10}})
    recs = json.loads(store.read_text().splitlines()[-1])
    assert recs["tool"] == "warp-lang"
    assert recs["sim"] == "particle-drop"
    assert recs["device"] == "cuda:0"
    assert recs["num_particles"] == 1000
    assert recs["wall_ms"] == 1.5
    assert "ts" in recs and "error" not in recs


def test_record_run_keeps_domain_errors(tmp_path, monkeypatch):
    store = tmp_path / "runs.jsonl"
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(store))
    RUN.record_run({"device": "cuda:0", "version": "1.15.0", "sim": None,
                    "error": "RuntimeError: boom"})
    recs = json.loads(store.read_text().splitlines()[-1])
    assert recs["error"] == "RuntimeError: boom"
    assert recs["wall_ms"] is None


def test_record_run_is_best_effort(tmp_path, monkeypatch):
    # Unwritable store (directory in place of the file) must never raise.
    d = tmp_path / "blocker"
    d.mkdir()
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(d / "runs.jsonl"))
    RUN.record_run({"device": "cpu", "version": None, "sim": {},
                    "error": "x"})  # must not raise


def test_read_history_newest_first_and_skips_malformed(tmp_path, monkeypatch):
    store = tmp_path / "runs.jsonl"
    store.write_text('{"device": "cpu", "wall_ms": 9.0}\nnot-json\n'
                     '{"device": "cuda:0", "wall_ms": 1.0}\n')
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(store))
    runs = RUN.read_history(None)
    assert [r["device"] for r in runs] == ["cuda:0", "cpu"]  # newest first
    assert RUN.read_history(1) == [runs[0]]


def test_read_history_missing_store_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(tmp_path / "none.jsonl"))
    assert RUN.read_history(None) == []


def test_history_bounded_to_max_records(tmp_path, monkeypatch):
    store = tmp_path / "runs.jsonl"
    # Pre-seed past the bound; record_run must keep only the newest 1000.
    seed = [{"device": "cpu", "wall_ms": i, "n": i} for i in range(RUN.MAX_RUN_RECORDS + 5)]
    store.write_text("\n".join(json.dumps(r) for r in seed) + "\n")
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(store))
    RUN.record_run({"device": "cuda:0", "version": None, "sim": None, "error": "new"})
    runs = RUN.read_history(None)
    assert len(runs) == RUN.MAX_RUN_RECORDS
    assert runs[0]["error"] == "new"          # newest kept
    assert runs[-1]["n"] == seed[6]["n"]      # first 6 dropped (1006 → 1000)


def test_history_stats_per_device_median(tmp_path, monkeypatch):
    store = tmp_path / "runs.jsonl"
    lines = [{"device": "cpu", "wall_ms": 900.0},
             {"device": "cpu", "wall_ms": 1000.0},
             {"device": "cuda:0", "wall_ms": 2.0},
             {"device": "cuda:0", "wall_ms": 4.0},
             {"device": "cuda:0", "wall_ms": 3.0},
             {"device": "cpu"}]  # no wall_ms — excluded from stats, counted in runs
    store.write_text("\n".join(json.dumps(r) for r in lines) + "\n")
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(store))
    stats = RUN.history_stats(RUN.read_history(None))
    assert stats["count"] == 6
    assert stats["by_device"]["cpu"]["median_wall_ms"] == 950.0  # mean of 900+1000
    assert stats["by_device"]["cuda:0"]["median_wall_ms"] == 3.0
    assert stats["by_device"]["cuda:0"]["count"] == 3


# ── science.py: the documented run syntax must work (SDD-301 fix) ───────────

# The fake runner records its exact argv to $FAKE_RUNNER_OUT so in-process
# tests can assert forwarding without importing warp.
FAKE_RUNNER = '''#!/usr/bin/env python3
import json, os, sys
out = os.environ["FAKE_RUNNER_OUT"]
with open(out, "w") as f:
    json.dump(sys.argv[1:], f)
'''


@pytest.fixture
def fake_runner(tmp_path, monkeypatch):
    fake = tmp_path / "fake-runner.py"
    fake.write_text(FAKE_RUNNER)
    out = tmp_path / "argv.json"
    monkeypatch.setattr(SCI, "WARP_RUNNER", fake)
    monkeypatch.setenv("FAKE_RUNNER_OUT", str(out))
    return out


def test_run_accepts_documented_syntax(fake_runner):
    # The man-page syntax that used to fail with "unrecognized arguments".
    rc = SCI.main(["run", "--device", "cuda", "--particles", "1000",
                   "--steps", "20", "--json"])
    assert rc == 0
    argv = json.loads(fake_runner.read_text())
    assert argv == ["run", "--device", "cuda", "--particles", "1000",
                    "--steps", "20", "--json"]


def test_run_forwards_only_set_flags(fake_runner):
    rc = SCI.main(["run", "--json"])
    assert rc == 0
    argv = json.loads(fake_runner.read_text())
    assert argv == ["run", "--json"]  # config file supplies the defaults


def test_run_rejects_bad_device(fake_runner):
    with pytest.raises(SystemExit) as exc:
        SCI.main(["run", "--device", "bogus"])
    assert exc.value.code == 2  # argparse usage error


def test_history_delegates_to_runner_with_limit(fake_runner):
    rc = SCI.main(["history", "--limit", "5", "--json"])
    assert rc == 0
    argv = json.loads(fake_runner.read_text())
    assert argv == ["history", "--limit", "5", "--json"]


# ── per-tool readiness detection (SDD-301) ───────────────────────────────────

def test_detect_import_present(tmp_path, monkeypatch):
    (tmp_path / "fake_mod_sdd301.py").write_text("x = 1\n")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    got = SCI.detect_tool({"id": "t", "install": {"method": "pip", "ref": "fake_mod_sdd301"},
                           "detect": {"method": "import", "ref": "fake_mod_sdd301"}})
    assert got["state"] == "installed"


def test_detect_import_absent_is_downloadable(monkeypatch):
    got = SCI.detect_tool({"id": "t", "install": {"method": "pip", "ref": "definitely_not_a_module_zz"},
                           "detect": {"method": "import", "ref": "definitely_not_a_module_zz"}})
    assert got["state"] == "downloadable"


def test_detect_import_unsafe_ref_is_unknown(monkeypatch):
    # A catalog typo with shell metacharacters must NEVER be interpolated —
    # it reports unknown instead.
    got = SCI.detect_tool({"id": "t", "install": {"method": "pip", "ref": "bad;rm"},
                           "detect": {"method": "import", "ref": "bad;rm"}})
    assert got["state"] == "unknown"


def test_detect_hf_weights_present(monkeypatch, tmp_path):
    hub = tmp_path / "hub" / "models--org--name" / "snapshots" / "abc123"
    hub.mkdir(parents=True)
    (hub / "model.bin").write_bytes(b"x")
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.delenv("SOVEREIGN_OS_MODELS_DIR", raising=False)
    got = SCI.detect_tool({"id": "t", "install": {"method": "hf", "ref": "org/name"},
                           "detect": {"method": "hf", "ref": "org/name"}})
    assert got["state"] == "artifacts-present"


def test_detect_hf_weights_plus_import_is_installed(monkeypatch, tmp_path):
    hub = tmp_path / "hub" / "models--org--name" / "snapshots" / "abc123"
    hub.mkdir(parents=True)
    (hub / "model.bin").write_bytes(b"x")
    (tmp_path / "fake_mod_sdd301.py").write_text("x = 1\n")
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    monkeypatch.delenv("SOVEREIGN_OS_MODELS_DIR", raising=False)
    got = SCI.detect_tool({"id": "t", "install": {"method": "hf", "ref": "org/name"},
                           "detect": {"method": "hf", "ref": "org/name",
                                      "import_module": "fake_mod_sdd301"}})
    assert got["state"] == "installed"


def test_detect_hf_missing_is_downloadable(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.delenv("SOVEREIGN_OS_MODELS_DIR", raising=False)
    got = SCI.detect_tool({"id": "t", "install": {"method": "hf", "ref": "org/absent"},
                           "detect": {"method": "hf", "ref": "org/absent"}})
    assert got["state"] == "downloadable"
    assert got["install_cmd"] == "hf download org/absent"


def test_detect_hf_vault_fallback(monkeypatch, tmp_path):
    vault = tmp_path / "vault" / "name"
    vault.mkdir(parents=True)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "no-hub"))
    monkeypatch.setenv("SOVEREIGN_OS_MODELS_DIR", str(tmp_path / "vault"))
    got = SCI.detect_tool({"id": "t", "install": {"method": "hf", "ref": "org/name"},
                           "detect": {"method": "hf", "ref": "org/name"}})
    assert got["state"] == "artifacts-present"


def test_detect_checkout_present_and_absent(monkeypatch, tmp_path):
    tree = tmp_path / "checkout"
    tree.mkdir()
    t_present = {"id": "t", "install": {"method": "github", "ref": "https://x/y"},
                 "detect": {"method": "checkout", "ref": str(tree)}}
    assert SCI.detect_tool(t_present)["state"] == "installed"
    t_absent = {"id": "t", "install": {"method": "github", "ref": "https://x/y"},
                "detect": {"method": "checkout", "ref": str(tmp_path / "nope")}}
    assert SCI.detect_tool(t_absent)["state"] == "downloadable"
    assert SCI.detect_tool(t_absent)["install_cmd"] == "git clone https://x/y"


def test_status_json_has_tools_status(tmp_path, monkeypatch):
    cp = subprocess.run([PY, str(SCIENCE), "status", "--json"],
                        capture_output=True, text=True, check=False,
                        env={**os.environ, "SOVEREIGN_OS_SCIENCE_RUNS": str(tmp_path / "r.jsonl")})
    assert cp.returncode == 0, cp.stderr
    d = json.loads(cp.stdout)
    assert "tools_status" in d
    assert len(d["tools_status"]) >= 7
    for s in d["tools_status"]:
        assert s["state"] in {"installed", "artifacts-present", "downloadable", "unknown"}


# ── science-api gpu context ──────────────────────────────────────────────────

def test_gpu_context_degrades_honestly_without_nvidia_smi(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent-path-for-test")
    ctx = API_MOD.gpu_context()
    assert ctx["available"] is False
    assert "reason" in ctx


def test_gpu_context_reads_nvidia_smi_when_present():
    if subprocess.run(["sh", "-c", "command -v nvidia-smi"], capture_output=True).returncode != 0:
        pytest.skip("nvidia-smi not present on this host (dev/CI box)")
    ctx = API_MOD.gpu_context()
    assert ctx["available"] is True
    assert len(ctx["gpus"]) >= 1
    g = ctx["gpus"][0]
    for key in ("index", "name", "memory_total_mib", "memory_free_mib", "utilization_pct"):
        assert key in g


def test_assemble_science_exposes_new_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_SCIENCE_RUNS", str(tmp_path / "r.jsonl"))
    d = API_MOD.assemble_science()
    for key in ("tools", "integrated_tools", "warp", "tools_status",
                "recent_runs", "run_stats", "gpu"):
        assert key in d, f"missing key: {key}"


def test_api_self_check_reports_new_keys():
    cp = subprocess.run([PY, str(API), "--self-check"],
                        capture_output=True, text=True, check=False,
                        env={**os.environ,
                             "SOVEREIGN_OS_SCIENCE_RUNS": "/tmp/so-science-selfcheck-runs.jsonl"})
    assert cp.returncode == 0, cp.stderr
    d = json.loads(cp.stdout)
    assert d["version"] == "0.2.0"
    for key in ("tools_status_count", "recent_runs", "run_stats_count",
                "gpu_available", "gpu_count"):
        assert key in d
