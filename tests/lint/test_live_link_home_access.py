"""The dev live-link must remain usable by hardened systemd panel services."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "install" / "link-operator-cli.sh"


def test_live_link_binds_a_home_checkout_read_only_for_operator_services():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "ProtectHome=tmpfs" in body
    assert "BindReadOnlyPaths=%s" in body
    assert "/home/*" in body
    assert "/usr/local/lib/sovereign-os/" in body
    assert "/usr/lib/systemd/system/sovereign-*.service" in body
    assert "systemctl daemon-reload" in body
    assert "sovereign-lm-orchestration-api.service" in body
    assert "sovereign-livereload-broker.service" in body
    assert "sovereign-control-exec-api.service" in body


def test_live_link_does_not_relax_home_access_for_non_home_sources():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "*) return 0" in body
