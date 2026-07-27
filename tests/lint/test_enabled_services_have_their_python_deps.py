"""A service that is ENABLED must be able to import what it needs.

2026-07-27. install-gui-dashboards.sh enables a set of units at install time;
each ExecStarts a Python entrypoint under /usr/local/lib/sovereign-os. If one of
those imports a module Debian never installed, the unit fails on start — and 67
sovereign units carry Restart=, so it fails forever rather than once.

Today's audit came out clean, and the two third-party imports are clean for
DIFFERENT reasons worth preserving:

  * tomli   — imported as `try: import tomllib / except ImportError: import
              tomli as tomllib`. Debian 13 ships Python 3.13, where tomllib is
              stdlib, so nothing is needed.
  * grpc    — imported inside try/except with _GRPC_AVAILABLE, and its unit is
              NOT among those enabled at install time.

This lint keeps that true: any module imported UNGUARDED by an enabled unit's
entrypoint must correspond to an installed package.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
UNITS = REPO_ROOT / "systemd" / "system"
OPERATOR = REPO_ROOT / "scripts" / "operator"

# module -> Debian package providing it
KNOWN = {"yaml": "python3-yaml", "jsonschema": "python3-jsonschema",
         "grpc": "python3-grpcio", "tomli": "python3-tomli",
         "requests": "python3-requests"}


def installed() -> set[str]:
    out = subprocess.run(
        ["bash", "-c", ". scripts/install/lib/installed-system.sh; "
                       "sovereign_os_installed_packages"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    return set(out.split())


def enabled_units() -> set[str]:
    body = DASH.read_text(encoding="utf-8")
    return set(re.findall(r'enable_unit "?([a-z0-9-]+\.service)', body))


def unguarded_imports(py: Path) -> set[str]:
    """Top-level imports NOT wrapped in try/except ImportError."""
    tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
    def catches_import_error(handler: ast.ExceptHandler) -> bool:
        """A bare `except:` and `except Exception:` both catch ImportError.

        Restricting this to a literal `except ImportError` flagged a correctly
        guarded `import tomli` inside `except Exception:` (2026-07-27) — the
        lint was wrong, not the code.
        """
        if handler.type is None:                       # bare except:
            return True
        names = ([handler.type] if isinstance(handler.type, ast.Name)
                 else list(handler.type.elts) if isinstance(handler.type, ast.Tuple)
                 else [])
        return any(isinstance(n, ast.Name) and n.id in ("ImportError", "Exception",
                                                        "ModuleNotFoundError", "BaseException")
                   for n in names)

    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(catches_import_error(h) for h in node.handlers):
            for sub in ast.walk(node):
                guarded.add(id(sub))
    out: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return {m for m in out if m not in sys.stdlib_module_names}


def test_every_enabled_unit_can_import_what_it_needs():
    pkgs, problems = installed(), []
    for unit in sorted(enabled_units()):
        upath = UNITS / unit
        if not upath.exists():
            continue
        m = re.search(r"^ExecStart=.*?([\w./-]+\.py)", upath.read_text(encoding="utf-8"), re.M)
        if not m:
            continue
        entry = OPERATOR / Path(m.group(1)).name
        if not entry.exists():
            continue
        for mod in unguarded_imports(entry):
            pkg = KNOWN.get(mod)
            if pkg and pkg not in pkgs:
                problems.append(f"{unit}: {entry.name} imports {mod} -> needs {pkg}")
    assert not problems, (
        "enabled unit(s) import modules that are not installed; each fails on "
        f"start and Restart= makes it fail forever:\n  " + "\n  ".join(problems)
    )


def test_the_optional_imports_stay_optional():
    """grpc must remain guarded, since python3-grpcio is deliberately not shipped."""
    body = (OPERATOR / "weaver-grpc.py").read_text(encoding="utf-8")
    assert "_GRPC_AVAILABLE" in body and "except ImportError" in body, (
        "weaver-grpc must degrade when grpcio is absent; python3-grpcio is not "
        "in the installed package set"
    )
    assert "sovereign-weaver-grpc.service" not in DASH.read_text(encoding="utf-8"), (
        "if this unit is ever enabled at install time, python3-grpcio must be "
        "added to the shared package set first"
    )
