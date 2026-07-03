"""R500 (E11.M2++) — master-dashboard webapp surface contract lint.

Closes the master-dashboard webapp:FUTURE waiver. Raises the master-
dashboard surface count from 6 → 7 shipped surfaces (core / cli / tui /
service / api / mcp / webapp). Third commit in the tier-3 surface-
expansion arc for the §1g-named modules.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The webapp surface is a single-file monochrome SPA served by the R498
API daemon under /webapp/ from the SAME host:port binding as the JSON
endpoints. Operator-§1g UX rule: zero external dependencies, no CDN
fetches, no third-party fonts, no JS framework. Read-only mirror of
`sovereign-osctl master-dashboard <verb>` — mutation verbs stay CLI-only
(operator §17 sacrosanct sovereignty boundary).
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "master-dashboard-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "MASTER_DASHBOARD_API_BIND": "127.0.0.1",
        "MASTER_DASHBOARD_API_PORT": str(port),
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
    raise RuntimeError("API daemon failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R500 webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    """Single-file SPA must declare HTML5 doctype + lang + viewport."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must declare <!DOCTYPE html> on the first line"
    )
    assert "<html lang=" in body, "webapp must set <html lang=...>"
    assert 'name="viewport"' in body, "webapp must declare viewport"


def test_webapp_carries_sovereign_meta_tags():
    """Operator-§1g identity meta tags MUST be present so any consumer
    inspecting the HTML can confirm the standing-rule provenance."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "master-dashboard-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert 'name="x-sovereign-standing-rule"' in body
    assert "We do not minimize anything." in body, (
        "webapp must quote the operator §1g standing rule verbatim"
    )


def test_webapp_has_zero_external_dependencies():
    """Operator-§1g UX rule: NO CDN fetches, NO third-party fonts, NO
    cross-origin script tags. Same-origin fetch() against /version
    /routes /collisions /health /discover ONLY."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    forbidden_hosts = [
        "https://cdn.",
        "http://cdn.",
        "https://cdnjs.",
        "https://unpkg.",
        "https://fonts.googleapis.",
        "https://fonts.gstatic.",
        "https://ajax.googleapis.",
        "https://code.jquery.",
        "https://stackpath.",
        "https://maxcdn.",
        "https://bootstrapcdn.",
        "https://use.fontawesome.",
        "//cdn.",
    ]
    for host in forbidden_hosts:
        assert host not in body, (
            f"webapp must NOT reference external host {host!r} "
            f"(operator-§1g zero-CDN rule)"
        )
    # Stricter: no <script src="http..."> or <link href="http...">
    # to any external resource.
    import re
    ext_script = re.search(r'<script[^>]+src="https?://', body)
    assert ext_script is None, (
        f"webapp contains external <script src=...>: "
        f"{ext_script.group(0) if ext_script else ''}"
    )
    ext_link = re.search(r'<link[^>]+href="https?://', body)
    assert ext_link is None, (
        f"webapp contains external <link href=...>: "
        f"{ext_link.group(0) if ext_link else ''}"
    )


def test_webapp_fetches_only_same_origin_endpoints():
    """The webapp's JS MUST fetch only same-origin paths (the R498
    daemon's read-only endpoints). Anything else is a sovereignty leak."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    import re
    # Find all fetch() targets — they MUST be paths starting with /,
    # not absolute URLs.
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), (
            f"webapp fetch() target {target!r} is not same-origin "
            f"(must start with '/')"
        )
        assert "//" not in target, (
            f"webapp fetch() target {target!r} looks like a "
            f"protocol-relative URL — same-origin only"
        )


def test_webapp_advertises_read_only_endpoints():
    """The webapp must wire against the 5 read-only R498 endpoints
    (mutation verbs stay CLI-only — operator §17 sovereignty boundary)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/routes", "/collisions",
                 "/health", "/discover", "/catalog"):
        assert path in body, (
            f"webapp must wire against R498 endpoint {path!r}"
        )
    # And it must NOT wire against mutation verbs.
    for forbidden in ("/render", "/install", "/apply"):
        # Allow as substring in human-readable footer text mentioning
        # the CLI; reject only as a fetch() target.
        import re
        m = re.search(rf'fetch\(\s*["\']{forbidden}', body)
        assert m is None, (
            f"webapp leaks mutation verb {forbidden!r} as fetch() "
            f"target (§17 sovereignty violation)"
        )


def test_api_daemon_serves_webapp_path():
    """Live-spawn the R498 daemon and assert GET /webapp/ returns 200
    text/html with the §1g standing rule embedded."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            assert r.status == 200
            ctype = r.headers.get("Content-Type", "")
            assert "text/html" in ctype, (
                f"/webapp/ must return text/html; got {ctype!r}"
            )
            body = r.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "<!doctype html>" in body
            assert "master-dashboard" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "master-dashboard-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_webapp_aliases():
    """/webapp, /webapp/, /webapp/index.html all resolve to the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for path in ("/webapp", "/webapp/", "/webapp/index.html"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=3
            ) as r:
                assert r.status == 200, (
                    f"{path} did not return 200; got {r.status}"
                )
                assert "text/html" in r.headers.get("Content-Type", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    """R500 /version response MUST list 'webapp' in surfaces[]."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", []), (
            f"/version must advertise 'webapp' surface; got {data}"
        )
        assert "R500" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R500; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_master_dashboard_surface_map_extended_to_webapp():
    """R500 extends master-dashboard surface-map to 7 shipped surfaces —
    webapp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "master-dashboard", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage master-dashboard failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 7, (
        f"master-dashboard must be at >=7 surfaces post-R500; "
        f"got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None, (
        "master-dashboard coverage matrix missing 'webapp' row"
    )
    assert webapp_row.get("state") == "shipped", (
        f"master-dashboard webapp surface must be shipped; got {webapp_row}"
    )


def test_webapp_renders_described_catalog():
    """SDD-045 Phase B — the described global view. The webapp MUST carry
    the 'all dashboards — described' section that fetches /catalog and
    renders a REAL description next to every label (the operator's 'IN THE
    LIST WHERE IS THE DESCRIPTIONS' fix). Static-source check: the section
    header, the render function, the container, and the /catalog fetch are
    all present."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "all dashboards — described" in body, (
        "webapp missing the described-global-view section header"
    )
    assert "renderCatalog" in body, (
        "webapp missing the renderCatalog() function"
    )
    assert 'id="catalog-body"' in body, (
        "webapp missing the catalog-body container"
    )
    assert 'fetchJSON("/catalog")' in body, (
        "webapp must fetch the described /catalog endpoint"
    )
    # the render must be wired into the refresh cycle
    assert "renderCatalog();" in body, (
        "renderCatalog() must be called from refresh()"
    )


def test_api_daemon_serves_described_catalog_in_webapp():
    """Live-spawn: GET /webapp/ contains the described section AND GET
    /catalog returns described entries — proving the list the operator
    looks at now shows real descriptions, not bare slugs."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            html = r.read().decode("utf-8")
        assert "all dashboards — described" in html
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/catalog", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert data.get("dashboard_count", 0) >= 30, (
            f"/catalog should describe the full surface; got {data.get('dashboard_count')}"
        )
        # every served entry carries a real description
        undescribed = [d["slug"] for d in data["dashboards"]
                       if len((d.get("description") or "").strip()) < 30]
        assert not undescribed, (
            f"/catalog served entries with no real description: {undescribed}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_webapp_surface_quotes_standing_rule_in_footer():
    """The webapp footer MUST quote operator §1g verbatim — the
    standing-rule provenance is sacrosanct, never paraphrased."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    # Find the footer block.
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer, (
        "webapp footer must quote §1g standing rule verbatim"
    )
    assert "operator-§1g" in footer or "operator §1g" in footer or \
        "§1g" in footer, (
        "webapp footer must reference operator §1g provenance"
    )
