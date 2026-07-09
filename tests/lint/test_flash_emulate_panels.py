"""Contract lint for the flash + emulate operator panels (SDD-045).

These two panels turn build → emulate → flash into panel actions. This lint
locks the shape every one of them must keep so they never silently drift out
of the catalog / control-surface / API contract (mirrors
test_net_new_dashboards.py's _assert_live_panel, plus the execution-surface
specifics: a dedicated *-api.py daemon + a discoverable systemd unit).
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"
OPERATOR = REPO / "scripts" / "operator"
UNITS = REPO / "systemd" / "system"

# slug → (module-meta, data-endpoint, api-file, unit-file, port)
PANELS = {
    "flash": ("flash-webapp", "/flash.json", "flash-api.py",
              "sovereign-flash-api.service", "8122"),
    "emulate": ("emulate-webapp", "/emulate.json", "emulate-api.py",
                "sovereign-emulate-api.service", "8123"),
    "ups": ("ups-webapp", "/ups.json", "ups-api.py",
            "sovereign-ups-api.service", "8124"),
}


def _catalog_entry(slug: str) -> dict:
    """Tiny flow-map extractor — one entry per line, {slug: X, ...}."""
    text = CATALOG.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.search(r"\{slug:\s*" + re.escape(slug) + r"\b", line)
        if not m:
            continue
        entry = {}
        for k in ("category", "label", "path", "api", "status"):
            mm = re.search(rf"{k}:\s*([^,}}]+)", line)
            if mm:
                entry[k] = mm.group(1).strip().strip('"')
        dm = re.search(r'description:\s*"((?:[^"\\]|\\.)*)"', text[m.start():])
        if dm:
            entry["description"] = dm.group(1)
        return entry
    raise AssertionError(f"dashboard-catalog.yaml has no entry for {slug!r}")


def test_panels_are_live_control_surfaces():
    for slug, (module, endpoint, *_rest) in PANELS.items():
        html = (WEBAPP / slug / "index.html")
        assert html.is_file(), f"missing panel webapp/{slug}/index.html"
        body = html.read_text(encoding="utf-8")
        assert f'content="{module}"' in body, f"{slug}: missing x-sovereign-module {module}"
        assert "We do not minimize anything." in body, f"{slug}: missing the standing rule"
        assert endpoint in body, f"{slug}: panel must fetch its real data ({endpoint})"
        assert 'id="control-surface"' in body, f"{slug}: must be a control surface"
        assert f"filterSlug:'{slug}'" in body or f'filterSlug:"{slug}"' in body, \
            f"{slug}: control surface must filter to its own slug"


def test_catalog_entries_are_live_and_correct():
    for slug, (_m, _e, api, *_r) in PANELS.items():
        e = _catalog_entry(slug)
        assert e.get("status") == "live", f"{slug}: catalog status must be live"
        assert e.get("path") == f"/{slug}/", f"{slug}: catalog path must be /{slug}/"
        assert e.get("category") == "hardware", f"{slug}: belongs in category hardware"
        assert len(e.get("description", "")) >= 30, f"{slug}: description too short"
        assert e.get("api", "").startswith("sovereign-"), f"{slug}: must name its sovereign-*-api"


def test_each_panel_has_a_daemon_serving_its_contract():
    for slug, (_m, endpoint, api, _unit, _port) in PANELS.items():
        src = (OPERATOR / api)
        assert src.is_file(), f"missing daemon scripts/operator/{api}"
        body = src.read_text(encoding="utf-8")
        assert endpoint.strip("/").split(".")[0] in body, \
            f"{api}: must serve {endpoint}"
        assert "/healthz" in body, f"{api}: must answer /healthz (panel.sh probes it)"
        assert "def assemble_" in body, f"{api}: must assemble its data payload"


def test_flash_never_reimplements_dd_and_guards_devices():
    """The flash daemon must go through the gated CLI (never raw dd) and must
    re-validate the target device server-side before any run."""
    body = (OPERATOR / "flash-api.py").read_text(encoding="utf-8")
    assert "install" in body and "image" in body, "flash must shell to `install image`"
    assert "flashable" in body, "flash must classify devices for safety"
    assert "protected_disks" in body, "flash must compute protected (system) disks"
    # server never trusts the picker: it recomputes flashable before running
    assert 'match["flashable"]' in body, "flash must re-validate the target server-side"


def test_emulate_keeps_the_image_pristine_and_interactive():
    body = (OPERATOR / "emulate-api.py").read_text(encoding="utf-8")
    assert "-snapshot" in body, "emulate must attach the disk with -snapshot (pristine .raw)"
    assert "/api/emulate/input" in body, "emulate must accept interactive keystrokes"
    assert "/api/emulate/console" in body, "emulate must stream the serial console"
    assert "-serial" in body and "stdio" in body, "emulate must bridge the guest serial"


def test_units_exist_and_are_port_discoverable():
    for slug, (_m, _e, _api, unit, port) in PANELS.items():
        u = (UNITS / unit)
        assert u.is_file(), f"missing systemd unit {unit}"
        body = u.read_text(encoding="utf-8")
        # panel.sh discovers the daemon by grepping Environment=…PORT=
        assert re.search(rf"Environment=[A-Z_]*PORT={port}\b", body), \
            f"{unit}: must declare its PORT={port} for panel.sh discovery"
        # ports must not collide with the hub/dashboard (8100/8443)
        assert port not in ("8100", "8443"), f"{unit}: port collides with hub/dashboard"
        for clause in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true"):
            assert clause in body, f"{unit}: missing hardening clause {clause}"
