"""R510 (E11.M5++) — global-history read-only REST API surface contract lint.

Closes the global-history api waiver AND the prior service "not
applicable — query surface, read-only" waiver. Raises the
global-history surface count from 4 → 6 shipped surfaces (core / cli
/ tui / dashboard / api / service). First commit in the
global-history tier-3 surface-expansion arc — same shape as the
auth-tier R501 / edge-firewall R504 / network-edge R507 api-surface
openers.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The API surface mirrors the data the CLI exposes via
`sovereign-osctl global-history <verb>` — recent / summary / sources
/ delta as read-only endpoints across 6 source logs (apt / dpkg /
shell / osctl / events / modules). global-history has no mutation
verbs at any surface (operator §17 sovereignty boundary — the
underlying source logs are mutated by their owning processes, never
by this surface).
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "global-history-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system"
    / "sovereign-global-history-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "GLOBAL_HISTORY_API_BIND": "127.0.0.1",
        "GLOBAL_HISTORY_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("global-history-api failed to start within 6s")


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [
        ln for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    found_bind = False
    for ln in active:
        if "GLOBAL_HISTORY_API_BIND=" in ln:
            assert "GLOBAL_HISTORY_API_BIND=127.0.0.1" in ln, (
                f"active systemd line must bind 127.0.0.1: {ln}"
            )
            found_bind = True
        assert "GLOBAL_HISTORY_API_BIND=0.0.0.0" not in ln
    assert found_bind


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true",
                "PrivateTmp=true", "ProtectHome=true",
                "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, (
            f"R171 hardening key missing: {key}"
        )


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert data["module"] == "global-history-api"
        assert "R510" in data["shipped_in"]
        assert "api" in data["surfaces"]
        assert "service" in data["surfaces"]
        assert data["standing_rule"] == "We do not minimize anything."
        # The 6 KNOWN_SOURCES MUST be surfaced for operator visibility.
        for src in ("apt", "dpkg", "shell", "osctl", "events", "modules"):
            assert src in data["known_sources"], (
                f"/version known_sources must include {src!r}; "
                f"got {data['known_sources']}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_sources_endpoint():
    """`/sources` MUST enumerate ALL 6 known sources with path/exists
    status — operator §1g: full ladder visible, not minimized."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/sources", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "sources" in data
        srcs = {s["source"] for s in data["sources"]}
        for needed in ("apt", "dpkg", "shell", "osctl", "events",
                       "modules"):
            assert needed in srcs, (
                f"/sources missing source {needed!r}: {srcs}"
            )
        for entry in data["sources"]:
            for k in ("source", "path", "exists", "is_dir", "is_file"):
                assert k in entry, (
                    f"/sources entry missing field {k!r}: {entry}"
                )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_recent_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/recent?since=1h&limit=10",
            timeout=5,
        ) as r:
            data = json.loads(r.read())
        for k in ("since", "sources", "limit", "count", "events"):
            assert k in data, (
                f"/recent payload missing {k!r}: {list(data)}"
            )
        assert data["limit"] == 10
        assert isinstance(data["events"], list)
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_recent_endpoint_rejects_bad_limit():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/recent?limit=not-an-int",
                timeout=3,
            )
            assert False, "limit=not-an-int must 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read())
            assert "limit" in body.get("error", "").lower()
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_summary_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/summary", timeout=5
        ) as r:
            data = json.loads(r.read())
        assert data.get("window_days") == 7
        assert "sources" in data
        # All 6 KNOWN_SOURCES must appear in the summary — operator §1g
        # "We do not minimize anything." applies to the per-source
        # breakdown, even sources with zero events in the window.
        for src in ("apt", "dpkg", "shell", "osctl", "events", "modules"):
            assert src in data["sources"], (
                f"/summary sources missing {src!r}: "
                f"{list(data['sources'])}"
            )
            for k in ("count_7d", "last_event", "available"):
                assert k in data["sources"][src], (
                    f"/summary[{src}] missing {k!r}"
                )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_delta_endpoint_requires_since():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/delta", timeout=3
            )
            assert False, "/delta without ?since= must 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read())
            assert "since" in body.get("error", "").lower()
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_delta_endpoint_with_since():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/delta?since=1h", timeout=5
        ) as r:
            data = json.loads(r.read())
        for k in ("since", "sources", "count", "events"):
            assert k in data, (
                f"/delta payload missing {k!r}: {list(data)}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_unknown_endpoint_404():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/no-such-endpoint", timeout=3
            )
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
            assert "available" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_mutation_methods_405():
    """global-history has no mutation verbs at any surface — operator
    §17 sovereignty boundary. POST/PUT/DELETE/PATCH MUST 405 with the
    sovereignty-boundary disclaimer message."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/recent",
                method=method, data=b"",
            )
            try:
                urllib.request.urlopen(req, timeout=3)
                assert False, f"{method} must 405"
            except urllib.error.HTTPError as e:
                assert e.code == 405
                body = json.loads(e.read())
                assert "operator §17" in body.get("error", "")
                # The disclaimer must name at least one underlying
                # source so the operator sees what is/isn't this
                # daemon's mutation domain.
                err = body.get("error", "")
                assert any(s in err for s in
                           ("apt", "dpkg", "shell", "osctl",
                            "events", "modules"))
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_response_headers_carry_sovereign_identity():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            assert r.headers.get("X-Sovereign-Module") == \
                "global-history-api"
            ver = r.headers.get("X-Sovereign-Version", "")
            assert ver.startswith("1.")
            assert "R5" in ver
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_global_history_surface_map_extended():
    """R510 extends global-history surface-map to 6 shipped surfaces —
    api AND service MUST appear as shipped (the prior `service: not
    applicable — query surface, read-only` waiver is replaced by the
    actual systemd daemon shipped in this round)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "global-history", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 6, (
        f"global-history must be at >=6 surfaces post-R510; "
        f"got {entry}"
    )
    matrix = entry.get("matrix", [])
    api_row = next(
        (r for r in matrix if r.get("surface") == "api"), None
    )
    assert api_row is not None
    assert api_row.get("state") == "shipped"
    service_row = next(
        (r for r in matrix if r.get("surface") == "service"), None
    )
    assert service_row is not None
    assert service_row.get("state") == "shipped", (
        f"global-history service must be shipped post-R510 (prior "
        f"not-applicable waiver replaced); got {service_row}"
    )
