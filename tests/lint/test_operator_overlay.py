"""L1 lint — `scripts/lib/operator_overlay.py` library contract.

R283 (E5.M11) — every existing or future script can adopt this
helper to layer operator TOML overlays on top of compiled-in
defaults. The L1 test pins the API + behavior so future refactors
don't silently break adopters.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "lib" / "operator_overlay.py"

# Add the lib dir to sys.path so we can import the module under test.
sys.path.insert(0, str(LIB_PATH.parent))
import operator_overlay as oo  # noqa: E402


def test_library_module_exists():
    assert LIB_PATH.is_file(), f"missing {LIB_PATH}"
    assert "R283" in LIB_PATH.read_text() or "E5.M11" in LIB_PATH.read_text()


def test_public_api_shape():
    """Public functions the doctrine commits to."""
    for fname in ("resolve_overlay_path", "deep_merge", "collect_overlay_keys",
                  "load_with_overlay", "_env_var_name"):
        assert hasattr(oo, fname), f"missing {fname}"


def test_env_var_name_normalization():
    assert oo._env_var_name("ram-advisor") == "SOVEREIGN_OS_OVERLAY_RAM_ADVISOR"
    assert oo._env_var_name("memory.pressure") == "SOVEREIGN_OS_OVERLAY_MEMORY_PRESSURE"
    assert oo._env_var_name("a-b.c-d") == "SOVEREIGN_OS_OVERLAY_A_B_C_D"


def test_deep_merge_operator_wins():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    overlay = {"a": 99, "b": {"c": 200}}
    merged = oo.deep_merge(base, overlay)
    assert merged["a"] == 99, "operator scalar wins"
    assert merged["b"]["c"] == 200, "operator nested scalar wins"
    assert merged["b"]["d"] == 3, "default nested key preserved when overlay omits it"


def test_deep_merge_lists_replace_not_concat():
    """Lists REPLACE — operator must be able to clear a default list."""
    base = {"flags": ["a", "b", "c"]}
    overlay = {"flags": ["x"]}
    merged = oo.deep_merge(base, overlay)
    assert merged["flags"] == ["x"], "list replacement, not concatenation"


def test_deep_merge_empty_overlay_preserves_base():
    base = {"a": 1, "b": [1, 2]}
    merged = oo.deep_merge(base, {})
    assert merged == base


def test_collect_overlay_keys_dotted_paths():
    overlay = {
        "alpha": 1,
        "beta": {"nested1": 2, "nested2": {"deep": 3}},
        "gamma": [1, 2],
    }
    keys = oo.collect_overlay_keys(overlay)
    assert "alpha" in keys
    assert "beta.nested1" in keys
    assert "beta.nested2.deep" in keys
    assert "gamma" in keys


def test_resolve_overlay_path_explicit_wins():
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as fh:
        fh.write(b"k = 1")
        p = pathlib.Path(fh.name)
    try:
        assert oo.resolve_overlay_path("doesnt-matter", explicit=p) == p
    finally:
        p.unlink()


def test_resolve_overlay_path_returns_none_when_explicit_missing():
    assert oo.resolve_overlay_path("doesnt-matter",
                                    explicit=pathlib.Path("/no/such/file")) is None


def test_resolve_overlay_path_env_var_precedence():
    """Env var must beat /etc and dev paths."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as fh:
        fh.write(b"k = 1")
        env_path = pathlib.Path(fh.name)
    try:
        os.environ["SOVEREIGN_OS_OVERLAY_PRECEDENCE_TEST"] = str(env_path)
        resolved = oo.resolve_overlay_path("precedence-test")
        assert resolved == env_path
    finally:
        os.environ.pop("SOVEREIGN_OS_OVERLAY_PRECEDENCE_TEST", None)
        env_path.unlink()


def test_load_with_overlay_no_file_returns_defaults():
    """No overlay file → defaults pass through with _source marker."""
    DEFAULTS = {"threshold_pct": 25, "limit": 100}
    # Ensure no env var pollution
    os.environ.pop("SOVEREIGN_OS_OVERLAY_NONEXISTENT_LOAD_TEST", None)
    cfg = oo.load_with_overlay("nonexistent-load-test", DEFAULTS)
    assert cfg["threshold_pct"] == 25
    assert cfg["limit"] == 100
    assert cfg["_source"].startswith("(defaults")
    assert cfg["_overlay_keys"] == []


def test_load_with_overlay_layers_toml_on_defaults():
    """The core flexibility contract."""
    DEFAULTS = {
        "threshold_pct": 25,
        "limits": {"warn": 100, "critical": 200},
        "tags": ["default"],
    }
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as fh:
        fh.write("threshold_pct = 50\n")
        fh.write("[limits]\n")
        fh.write("critical = 999\n")
        p = pathlib.Path(fh.name)
    try:
        cfg = oo.load_with_overlay("layer-test", DEFAULTS, explicit_path=p)
        # Operator scalar wins.
        assert cfg["threshold_pct"] == 50
        # Operator nested win + sibling default preserved.
        assert cfg["limits"]["critical"] == 999
        assert cfg["limits"]["warn"] == 100, "warn not in overlay → default preserved"
        # Default-only key untouched.
        assert cfg["tags"] == ["default"]
        # Audit metadata.
        assert cfg["_source"] == str(p)
        assert set(cfg["_overlay_keys"]) == {"threshold_pct", "limits.critical"}
    finally:
        p.unlink()


def test_load_with_overlay_malformed_toml_falls_back_to_defaults():
    """Bad TOML must NOT take the script down — operator gets a parse
    error in the metadata but the defaults still apply."""
    DEFAULTS = {"key": "default_value"}
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as fh:
        fh.write("this is not toml [[[[ }}}}}\n")
        p = pathlib.Path(fh.name)
    try:
        cfg = oo.load_with_overlay("malformed-toml-test", DEFAULTS, explicit_path=p)
        assert cfg["key"] == "default_value"
        assert "_parse_error" in cfg
        assert cfg["_overlay_keys"] == []
    finally:
        p.unlink()


def test_load_with_overlay_preserves_metadata_on_empty_overlay():
    """Empty TOML is valid — must NOT mark _parse_error."""
    DEFAULTS = {"key": "default"}
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as fh:
        fh.write("# empty overlay\n")
        p = pathlib.Path(fh.name)
    try:
        cfg = oo.load_with_overlay("empty-overlay-test", DEFAULTS, explicit_path=p)
        assert cfg["key"] == "default"
        assert "_parse_error" not in cfg
        assert cfg["_overlay_keys"] == []
        assert cfg["_source"] == str(p)
    finally:
        p.unlink()


def test_doctrine_doc_present():
    """The library file MUST document the doctrine in its module
    docstring so future maintainers see why it exists."""
    body = LIB_PATH.read_text()
    assert "endless flexibility" in body.lower() or "flexibility-at-scale" in body.lower()
    assert "deep-merge" in body.lower() or "deep_merge" in body.lower()
    assert "operator" in body.lower()
