"""`.prom` textfile producer ⇄ direct-read consumer binding.

Some scripts read another tool's node_exporter textfile-collector output
DIRECTLY by filename via `_read_prom_lines("<name>.prom")` (power-status
reads gpu-watch's + thermal-watch's .prom to fold live draw/thermal into
its budget + advisories). node_exporter scrapes every *.prom by metric
name, so a producer-side filename that doesn't match the consumer's read
breaks ONLY this direct-read path — silently, with no scrape error.

This caught the thermal outlier: thermal-watch wrote `sovereign-thermal
.prom` while power-status read `sovereign-os-thermal-watch.prom` (the
universal `sovereign-os-*` convention every other emitter follows), so the
R265 thermal-breach dimension of the power advisories was dead. The
integration L3 test missed it because it hand-wrote a fixture under the
consumer's expected name instead of running the real producer.

This gate locks it: every filename read via `_read_prom_lines(...)` MUST be
written by some emitter (a `textfile_collector/<name>.prom` literal in the
source tree). A producer rename that diverges from a consumer fails here.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"

_READ = re.compile(r'_read_prom(?:_lines)?\(\s*["\']([a-z0-9-]+\.prom)["\']')
# Python producers: a textfile_collector path OR a `<dir> / "<name>.prom"`
# Path-join (e.g. _METRICS_DIR / "x.prom").
_WRITE_PATH = re.compile(r'textfile_collector/([a-z0-9-]+\.prom)')
_WRITE_JOIN = re.compile(r'/\s*["\']([a-z0-9-]+\.prom)["\']')
# Shell producers: `emit_metric_set <basename>` writes
# `${PREFIX}-<basename with _→->.prom` (PREFIX = sovereign-os). The
# recurrent hooks emit their .prom this way.
_WRITE_EMIT = re.compile(r'emit_metric_set\s+([a-z0-9_-]+)')


def _scan() -> tuple[dict[str, list[str]], set[str]]:
    consumed: dict[str, list[str]] = {}
    produced: set[str] = set()
    for f in SCRIPTS.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        txt = f.read_text(errors="ignore")
        for name in set(_READ.findall(txt)):
            consumed.setdefault(name, []).append(
                str(f.relative_to(REPO_ROOT)))
        produced |= set(_WRITE_PATH.findall(txt))
        produced |= set(_WRITE_JOIN.findall(txt))
    for f in SCRIPTS.rglob("*.sh"):
        txt = f.read_text(errors="ignore")
        for base in _WRITE_EMIT.findall(txt):
            produced.add(f"sovereign-os-{base.replace('_', '-')}.prom")
    return consumed, produced


def test_some_prom_reads_exist():
    consumed, _ = _scan()
    assert len(consumed) >= 2, (
        f"parsed only {len(consumed)} _read_prom_lines consumers — parser "
        f"may be broken"
    )


def test_every_consumed_prom_is_produced():
    consumed, produced = _scan()
    dangling = {
        name: sorted(set(srcs))
        for name, srcs in consumed.items()
        if name not in produced
    }
    assert not dangling, (
        "`.prom` file(s) read via _read_prom_lines that NO emitter writes "
        "(producer filename diverged from the consumer — the direct-read "
        "integration is silently dead):\n"
        + "\n".join(f"  {n}  ←  {', '.join(s)}"
                    for n, s in sorted(dangling.items()))
        + "\nAlign the producer's textfile_collector/<name>.prom to the "
        "name the consumer reads (the sovereign-os-* convention)."
    )
