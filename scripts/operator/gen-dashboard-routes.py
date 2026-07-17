#!/usr/bin/env python3
"""gen-dashboard-routes.py — generate config/dashboard-routes.yaml (2026-07-17).

F-2026-072: the master-dashboard reverse-proxy aggregator's route table
(`DASHBOARD_ROUTES` in scripts/operator/master-dashboard.py) was a 26-entry
hand-maintained dict covering only d-01..d-20 + a few infra upstreams, while the
cockpit had grown to 55 webapp panels. The ~29 non-`d` panels + d-21..d-29 were
reachable only via the :8100 static hub — invisible to the aggregator. A stale
hand-maintained table is exactly the drift the repo's generated-config + CI-lock
pattern (panel-api-routes.yaml, backlog INDEX, cockpit consumption-map) exists to
kill. So the table is now GENERATED from the authoritative sources and drift-
locked by tests/lint/test_dashboard_routes.py.

Sources joined (nothing minimized — every panel AND every infra upstream kept):

  * config/dashboard-catalog.yaml — the authoritative panel list. Each panel
    with an `api: sovereign-<stem>` is fronted; its upstream PORT is the panel
    API's OWN `<X>_PORT` default parsed from scripts/operator/<stem>.py (the
    same single source panel.sh + gen-panel-routes read), its subpath is the
    catalog `path`, its label the catalog `label`. Panels with no api (static /
    CLI-backed: course, models-catalog, …) are served by the static hub, not the
    aggregator — they are listed under `static_only:` for operator visibility,
    not proxied.
  * INFRA_ROUTES (below) — the non-panel upstreams the aggregator also fronts:
    the 3 Trinity engines (bitnet.cpp + 2× vLLM), the SDD-011 deterministic
    router daemon, Grafana, and the node_exporter textfile collector. These are
    real services with no catalog panel; hand-declared here so a catalog-only
    generation never drops them.

Run `python3 scripts/operator/gen-dashboard-routes.py`; `--check` exits non-zero
if the committed table is stale.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "scripts" / "operator"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"
OUT = REPO / "config" / "dashboard-routes.yaml"

# The hub itself (build-configurator-api serves the :8100 static surface). Its
# catalog `api` alias is `sovereign-dashboards`; it is the proxy, never a
# fronted upstream — exclude it exactly as gen-panel-routes.py excludes it.
HUB_API = "sovereign-dashboards"

# Non-panel infra upstreams the aggregator fronts. Hand-declared: these are real
# running services with NO catalog panel, so a catalog-only pass can't see them.
# Keeping them here is the "we do not minimize" guard — the SDD-011 router daemon
# healthz, the Trinity engines, Grafana, and node_exporter stay routable.
INFRA_ROUTES = [
    {"slug": "trinity-pulse", "port": 8081, "healthz_path": "/v1/models",
     "subpath": "/pulse/", "label": "Trinity Pulse (bitnet.cpp HTTP)",
     "source_repo": "sovereign-os"},
    {"slug": "trinity-logic-engine", "port": 8082, "healthz_path": "/v1/models",
     "subpath": "/logic/", "label": "Trinity Logic Engine (vLLM)",
     "source_repo": "sovereign-os"},
    {"slug": "trinity-oracle-core", "port": 8083, "healthz_path": "/v1/models",
     "subpath": "/oracle/", "label": "Trinity Oracle Core (vLLM Blackwell)",
     "source_repo": "sovereign-os"},
    {"slug": "router-engine", "port": 8080, "healthz_path": "/healthz",
     "subpath": "/router-engine/", "label": "SDD-011 Deterministic Router daemon",
     "source_repo": "sovereign-os"},
    {"slug": "grafana-dashboard", "port": 3000, "healthz_path": "/api/health",
     "subpath": "/grafana/", "label": "Grafana", "source_repo": "sovereign-os"},
    {"slug": "metrics-textfile-collector", "port": 9100, "healthz_path": "/metrics",
     "subpath": "/metrics/", "label": "node_exporter (textfile collector)",
     "source_repo": "sovereign-os"},
]

_PORT_RE = re.compile(r'_PORT",\s*"(\d+)"')
# Each catalog dashboard is a single `- {slug: ..., ...}` YAML flow-map that may
# span multiple physical lines (the description wraps). Match from `- {` to the
# closing `}` non-greedily.
_ENTRY_RE = re.compile(r"- \{(.*?)\}", re.DOTALL)


def _parse_entry(blob: str) -> dict:
    """Parse the top-level `key: value` pairs of one catalog flow-map. Only the
    fields we need (slug/api/path/label/status) — values are simple scalars up
    to the next top-level comma; description/refs are ignored."""
    d: dict[str, str] = {}
    for key in ("slug", "api", "path", "label", "status", "category"):
        m = re.search(rf"\b{key}:\s*", blob)
        if not m:
            continue
        rest = blob[m.end():]
        if rest.startswith('"'):
            end = rest.find('"', 1)
            d[key] = rest[1:end]
        else:
            d[key] = rest.split(",")[0].split("\n")[0].strip()
    return d


def _api_port(api: str) -> int | None:
    """Resolve `sovereign-<stem>` → the `<X>_PORT` default in <stem>.py."""
    stem = api[len("sovereign-"):] if api.startswith("sovereign-") else api
    f = API_DIR / f"{stem}.py"
    if not f.is_file():
        return None
    m = _PORT_RE.search(f.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def _source_repo(api: str) -> str:
    """The selfdef read-only mirror panels are served by *-mirror-api daemons —
    tag their origin repo so the aggregator route table preserves the built-in
    table's source_repo provenance."""
    return "selfdef-mirror" if api.endswith("-mirror-api") else "sovereign-os"


def build() -> dict:
    """Return {routes: [...], static_only: [...], skipped: [...]}.

    routes    — proxied upstreams (infra + api-backed panels), subpath-sorted.
    static_only — catalog panels with no api (served by the :8100 static hub).
    skipped   — catalog panels whose api has no resolvable port (surfaced, not
                silently dropped).
    """
    catalog = CATALOG.read_text(encoding="utf-8")
    # Only the `dashboards:` section carries entries; `categories:` also uses
    # `- {…}` but never has a `path:`/`api:`, so _parse_entry yields no slug+api
    # match and they fall through harmlessly. Still, anchor to be safe.
    dash_start = catalog.index("\ndashboards:")
    body = catalog[dash_start:]

    panel_routes: list[dict] = []
    static_only: list[dict] = []
    skipped: list[dict] = []
    for blob in _ENTRY_RE.findall(body):
        e = _parse_entry(blob)
        slug = e.get("slug")
        if not slug:
            continue
        api = e.get("api")
        if not api:
            static_only.append({"slug": slug, "label": e.get("label", slug),
                                "reason": "no api (static hub / CLI-backed)"})
            continue
        if api == HUB_API:
            continue  # the hub is the proxy, never a fronted upstream
        port = _api_port(api)
        if port is None:
            skipped.append({"slug": slug, "api": api,
                            "reason": "api has no resolvable static port"})
            continue
        panel_routes.append({
            "slug": slug,
            "port": port,
            "healthz_path": "/healthz",
            "subpath": e.get("path", f"/{slug}/"),
            "label": e.get("label", slug),
            "source_repo": _source_repo(api),
        })

    routes = list(INFRA_ROUTES) + panel_routes
    routes.sort(key=lambda r: r["subpath"])
    return {"routes": routes, "static_only": static_only, "skipped": skipped}


def render() -> str:
    data = build()
    routes = data["routes"]
    static_only = data["static_only"]
    skipped = data["skipped"]
    lines = [
        "# config/dashboard-routes.yaml — GENERATED by",
        "# scripts/operator/gen-dashboard-routes.py (CI-locked by",
        "# tests/lint/test_dashboard_routes.py). The master-dashboard reverse-proxy",
        "# aggregator (scripts/operator/master-dashboard.py) fronts these",
        "# slug → upstream-port → subpath routes under one super-port. Regenerate",
        "# after adding/renaming a panel API or an infra upstream:",
        "#   python3 scripts/operator/gen-dashboard-routes.py",
        "#",
        f"# {len(routes)} proxied routes "
        f"({len(INFRA_ROUTES)} infra + {len(routes) - len(INFRA_ROUTES)} api-backed "
        f"panels); {len(static_only)} static-only panels (served by the :8100 hub, "
        "not proxied).",
        "",
        'schema_version: "1.0.0"',
        "",
        "routes:",
    ]
    for r in routes:
        lines.append(
            f'  - {{slug: {r["slug"]}, port: {r["port"]}, '
            f'healthz_path: "{r["healthz_path"]}", subpath: "{r["subpath"]}", '
            f'source_repo: {r["source_repo"]}, label: "{r["label"]}"}}'
        )
    lines.append("")
    lines.append("# Catalog panels with no dedicated API — reachable via the "
                 ":8100 static hub, not")
    lines.append("# the reverse-proxy aggregator. Listed for operator visibility "
                 "(not minimized away).")
    lines.append("static_only:")
    if static_only:
        for s in static_only:
            lines.append(f'  - {{slug: {s["slug"]}, label: "{s["label"]}"}}')
    else:
        lines.append("  []")
    if skipped:
        lines.append("")
        lines.append("# Catalog panels whose API declared no static port — "
                     "surfaced, never silently dropped.")
        lines.append("skipped:")
        for s in skipped:
            lines.append(f'  - {{slug: {s["slug"]}, api: {s["api"]}, '
                         f'reason: "{s["reason"]}"}}')
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != content:
            print(
                f"STALE: {OUT.relative_to(REPO)} — regenerate with "
                f"python3 scripts/operator/gen-dashboard-routes.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {OUT.relative_to(REPO)} is current")
        return 0
    OUT.write_text(content, encoding="utf-8")
    n = content.count("  - {slug:")
    print(f"wrote {OUT.relative_to(REPO)} ({n} route+static lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
