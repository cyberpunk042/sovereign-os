"""SDD-045 §5 (Phase E) — the net-new dashboards that fill the invisible
feature domains the operator flagged ("where are the Models / AVX /
orchestration"). Each is a real LIVE panel + a backing read-only endpoint +
a catalog entry flipped planned→live + the inlined control surface.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"
API = REPO / "scripts" / "operator" / "build-configurator-api.py"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"


def _entry(slug: str) -> dict:
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    for d in cat["dashboards"]:
        if d["slug"] == slug:
            return d
    raise AssertionError(f"catalog has no entry for {slug!r}")


def _assert_live_panel(slug: str, module_meta: str, data_endpoint: str):
    """Shared shape check for a net-new live dashboard."""
    panel = WEBAPP / slug / "index.html"
    assert panel.is_file(), f"missing panel webapp/{slug}/index.html"
    html = panel.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in html and module_meta in html, (
        f"{slug} panel missing its x-sovereign-module meta"
    )
    assert "We do not minimize anything." in html, f"{slug} panel missing the standing rule"
    assert data_endpoint in html, f"{slug} panel must fetch its real data ({data_endpoint})"
    assert 'id="control-surface"' in html, f"{slug} panel must be a control surface"
    entry = _entry(slug)
    assert entry.get("status") == "live", f"{slug} catalog status must be live"
    assert entry.get("path") == f"/{slug}/", f"{slug} catalog path must be /{slug}/"


def _api_serves(endpoint: str, loader: str):
    body = API.read_text(encoding="utf-8")
    assert endpoint in body and loader in body, (
        f"build-configurator-api must serve {endpoint} via {loader}"
    )


# ── models-catalog ───────────────────────────────────────────────────
def test_models_catalog_live():
    _assert_live_panel("models-catalog", "models-catalog-webapp", "/models-catalog.json")


def test_models_catalog_endpoint():
    _api_serves("/models-catalog.json", "_load_models_catalog")


# ── cpu-features (CPU / AVX-512 choice) ──────────────────────────────
def test_cpu_features_live():
    _assert_live_panel("cpu-features", "cpu-features-webapp", "/cpu-avx.json")


def test_cpu_features_endpoint():
    _api_serves("/cpu-avx.json", "_load_cpu_avx")


# ── orchestration (thinking router) ──────────────────────────────────
def test_orchestration_live():
    _assert_live_panel("orchestration", "orchestration-webapp", "/orchestration.json")


def test_orchestration_endpoint():
    _api_serves("/orchestration.json", "_load_orchestration")


# ── profile-generation ───────────────────────────────────────────────
def test_profile_generation_live():
    _assert_live_panel("profile-generation", "profile-generation-webapp", "/profile-generation.json")


def test_profile_generation_endpoint():
    _api_serves("/profile-generation.json", "_load_profile_generation")


# ── selfdef-management ───────────────────────────────────────────────
def test_selfdef_management_live():
    _assert_live_panel("selfdef-management", "selfdef-management-webapp", "/selfdef-management.json")


def test_selfdef_management_endpoint():
    _api_serves("/selfdef-management.json", "_load_selfdef")


# ── the whole Phase E set: no 'planned' models/selfdef domains remain ─
def test_all_five_net_new_dashboards_are_live():
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    live = {d["slug"] for d in cat["dashboards"] if d.get("status") == "live"}
    for slug in ("models-catalog", "cpu-features", "orchestration",
                 "profile-generation", "selfdef-management"):
        assert slug in live, f"net-new dashboard {slug} is not live yet"
