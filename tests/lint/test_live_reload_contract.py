"""R559 (SDD-203 / E11.M203) — dev live-reload contract.

Static guards for the `make panel` live-reload feature. The RUNTIME behaviour
(broker SSE relevant/irrelevant + reload-run same-PID self-re-exec) lives in
tests/nspawn/test_live_reload.sh; this lint pins the invariants that keep the
feature honest and safe without starting a process:

  * the in-panel client is present in the SDD-067 app-shell block, is
    LOOPBACK-GATED (inert in the shipped image), and is READ-ONLY
    (an EventSource stream — never fetch/XHR/POST/sendBeacon), so the app-shell
    non-mutation contract is preserved;
  * the broker port (8136) is consistent across the client, the broker, and
    panel.sh, and does NOT collide with any shipped sovereign-*-api unit port;
  * the two new dev daemons exist, carry a shebang, and byte-compile;
  * panel.sh routes every daemon through reload-run.py, starts the broker, and
    is ON by default (opt-out only).
"""
from __future__ import annotations

import py_compile
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"
RELOAD_RUN = REPO_ROOT / "scripts" / "operator" / "lib" / "reload-run.py"
BROKER = REPO_ROOT / "scripts" / "operator" / "livereload-broker.py"
PANEL_SH = REPO_ROOT / "scripts" / "operator" / "panel.sh"
SYSTEMD = REPO_ROOT / "systemd" / "system"
BROKER_UNIT = SYSTEMD / "sovereign-livereload-broker.service"
PROVISION_BAKE = REPO_ROOT / "scripts" / "build" / "provision-bake.sh"
INSTALL_GUI = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
MKOSI_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
PROFILE_SCHEMA = REPO_ROOT / "schemas" / "profile.schema.yaml"
SAIN01 = REPO_ROOT / "profiles" / "sain-01.yaml"

LR_BEGIN = "<!-- LIVERELOAD:BEGIN M203"
LR_END = "<!-- LIVERELOAD:END M203 -->"
BROKER_PORT = "8136"


def _client_block() -> str:
    src = SNIPPET.read_text(encoding="utf-8")
    i = src.find(LR_BEGIN)
    j = src.find(LR_END)
    assert i >= 0 and j >= 0, "LIVERELOAD client block markers missing in app-shell snippet"
    return src[i : j + len(LR_END)]


# ---------------------------------------------------------------- client block

def test_client_block_present_in_snippet_and_within_app_shell():
    """The client lives INSIDE the app-shell block (so sync-app-shell.py
    distributes it byte-identically) — between APP-SHELL:BEGIN and END."""
    src = SNIPPET.read_text(encoding="utf-8")
    ab = src.find("<!-- APP-SHELL:BEGIN M067 -->")
    ae = src.find("<!-- APP-SHELL:END M067 -->")
    lb = src.find(LR_BEGIN)
    assert ab >= 0 and ae >= 0, "app-shell markers missing"
    assert lb >= 0, "LIVERELOAD block missing"
    assert ab < lb < ae, "LIVERELOAD block must sit inside the app-shell block"


def test_client_is_read_only_no_mutation():
    """The client must be an EventSource stream ONLY — never fetch/XHR/POST/
    sendBeacon — so the app-shell non-mutation contract holds."""
    block = _client_block().lower()
    assert "new eventsource(" in block, "client must use EventSource"
    for forbidden in ("fetch(", "xmlhttprequest", "navigator.sendbeacon",
                      'method="post"', "method='post'", ".postmessage("):
        assert forbidden not in block, (
            f"live-reload client must be non-mutating; found: {forbidden}"
        )


def test_client_is_loopback_gated():
    """The client must no-op unless the page host is loopback — so it is inert
    in the shipped image (an appliance accessed over the LAN never connects)."""
    block = _client_block()
    assert "location.hostname" in block, "client must inspect location.hostname"
    assert "127.0.0.1" in block and "localhost" in block, (
        "client must gate on loopback hostnames (127.0.0.1 / localhost)"
    )


def test_client_targets_the_broker_port():
    block = _client_block()
    assert BROKER_PORT in block, f"client must target broker port {BROKER_PORT}"
    # It must give up after repeated failures (inert when no broker is running).
    assert "es.close()" in block, "client must close/give-up when the broker is absent"


def test_client_distributed_to_adopted_panels():
    """The block is synced into panels — assert on a couple of representative
    own-port panels (science, ups) that are viewed on their own ports."""
    for slug in ("science", "ups"):
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert LR_BEGIN in html and LR_END in html, (
            f"{slug}: live-reload client missing — run sync-app-shell.py --apply"
        )


# ---------------------------------------------------------------- daemons

def test_daemons_exist_with_shebang():
    for f in (RELOAD_RUN, BROKER):
        assert f.is_file(), f"missing {f}"
        first = f.read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith("#!"), f"{f.name} missing a shebang"


def test_daemons_byte_compile():
    for f in (RELOAD_RUN, BROKER):
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:  # pragma: no cover
            raise AssertionError(f"{f.name} failed to compile: {e}") from e


def test_broker_default_port_matches_client():
    src = BROKER.read_text(encoding="utf-8")
    assert f'"{BROKER_PORT}"' in src, (
        f"broker default port must be {BROKER_PORT} (matching the client)"
    )


def test_broker_binds_loopback_only():
    src = BROKER.read_text(encoding="utf-8")
    assert '"127.0.0.1"' in src, "broker must bind loopback only"


# ---------------------------------------------------------------- port collision

def _unit_ports() -> set[str]:
    ports: set[str] = set()
    for unit in SYSTEMD.glob("sovereign-*-api.service"):
        for m in re.finditer(r"[A-Z0-9_]*PORT=(\d{3,5})",
                              unit.read_text(encoding="utf-8")):
            ports.add(m.group(1))
    return ports


def test_broker_port_does_not_collide_with_any_api_unit():
    """8136 must be free — no shipped sovereign-*-api unit may declare it, or
    `make panel` would fight the broker for the port."""
    assert BROKER_PORT not in _unit_ports(), (
        f"broker port {BROKER_PORT} collides with a sovereign-*-api unit"
    )


# ---------------------------------------------------------------- panel.sh wiring

def test_panel_sh_wires_live_reload():
    src = PANEL_SH.read_text(encoding="utf-8")
    assert "scripts/operator/lib/reload-run.py" in src, (
        "panel.sh must launch daemons through reload-run.py"
    )
    assert "scripts/operator/livereload-broker.py" in src, (
        "panel.sh must start the live-reload broker"
    )
    assert 'LR_WRAP[@]' in src, "panel.sh must route daemon launches through LR_WRAP"


def test_panel_sh_live_reload_on_by_default():
    """Default ON — the case default must treat unset as enabled, opt-out only."""
    src = PANEL_SH.read_text(encoding="utf-8")
    assert "${SOVEREIGN_OS_LIVERELOAD:-1}" in src, (
        "live-reload must default ON (SOVEREIGN_OS_LIVERELOAD:-1)"
    )


def test_panel_sh_still_parses():
    """A syntax slip in the wiring must not slip through."""
    r = subprocess.run(["bash", "-n", str(PANEL_SH)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"panel.sh bash -n failed: {r.stderr}"


# ---------------------------------------------------------------- installed-box wiring

def test_broker_service_unit_exists_and_runs_broker():
    """A flashed box runs the broker as a systemd service (not just make panel)."""
    assert BROKER_UNIT.is_file(), f"missing {BROKER_UNIT}"
    body = BROKER_UNIT.read_text(encoding="utf-8")
    assert "livereload-broker.py" in body, "broker unit must ExecStart the broker"
    # Fleet-hardening minimums (also covered by the fleet lint; asserted here so
    # the live-reload contract is self-contained).
    for clause in ("NoNewPrivileges=true", "ProtectSystem=strict",
                   "ProtectControlGroups=true", "PrivateTmp=true"):
        assert clause in body, f"broker unit missing hardening clause {clause}"


def test_shipped_api_units_stay_unwrapped():
    """The installed self-re-exec is applied via a generated DROP-IN, never by
    editing the shipped units — so the static units stay byte-identical and every
    per-unit ExecStart/hardening lint is untouched. Guard: no shipped unit's
    ExecStart routes through reload-run.py."""
    offenders = []
    for unit in SYSTEMD.glob("sovereign-*.service"):
        for line in unit.read_text(encoding="utf-8").splitlines():
            if line.startswith("ExecStart=") and "reload-run.py" in line:
                offenders.append(unit.name)
    assert not offenders, (
        f"shipped units must not bake reload-run into ExecStart (use the "
        f"provision-time drop-in instead): {offenders}"
    )


def test_provision_bake_wires_installed_livereload():
    """provision-bake §5c: gated on the bake flag, enables the broker and
    generates a drop-in that wraps ExecStart through reload-run + sets the env."""
    src = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_BAKE_LIVERELOAD" in src, "provision-bake must gate on the bake flag"
    assert "sovereign-livereload-broker.service" in src, "provision-bake must enable the broker"
    assert "lib/reload-run.py" in src, "provision-bake must wrap ExecStart through reload-run"
    assert "livereload.conf" in src, "provision-bake must write a livereload drop-in"
    assert "SOVEREIGN_OS_LIVERELOAD=1" in src, "the drop-in must enable reload-run via env"


def test_install_gui_dashboards_wires_installed_livereload():
    """The root-reflash / standalone path carries the same wiring."""
    src = INSTALL_GUI.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_BAKE_LIVERELOAD" in src
    assert "sovereign-livereload-broker.service" in src
    assert "lib/reload-run.py" in src and "livereload.conf" in src


def test_bake_flag_default_on_and_plumbed():
    """The bake flag defaults ON (opt-out), is exported by mkosi-emit, declared
    in the profile schema, and set in sain-01."""
    # provision paths default ON: ${SOVEREIGN_OS_BAKE_LIVERELOAD:-1}
    assert "${SOVEREIGN_OS_BAKE_LIVERELOAD:-1}" in PROVISION_BAKE.read_text(encoding="utf-8")
    assert "${SOVEREIGN_OS_BAKE_LIVERELOAD:-1}" in INSTALL_GUI.read_text(encoding="utf-8")
    # mkosi-emit exports it (default true in the parse + the export line)
    emit = MKOSI_EMIT.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_BAKE_LIVERELOAD" in emit and 'get("livereload", True)' in emit
    # schema declares it, sain-01 sets it on
    assert "livereload:" in PROFILE_SCHEMA.read_text(encoding="utf-8")
    assert "livereload: true" in SAIN01.read_text(encoding="utf-8")


if __name__ == "__main__":  # allow direct run
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
