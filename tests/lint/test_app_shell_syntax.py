"""A matching embed is insufficient: the shared shell must parse."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("shell_sync", ROOT / "scripts/webapp/sync-app-shell.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def test_canonical_shell_javascript_parses():
    sync.validate_scripts(sync.canonical_block())


def test_invalid_catalog_quote_is_rejected():
    with pytest.raises(ValueError, match="invalid"):
        sync.validate_scripts("<script>var x = {desc:'the profile's ports'};</script>")


def test_image_generation_content_survives_shell_sync():
    html = (ROOT / "webapp/image-generation/index.html").read_text()
    rendered, _ = sync.render(html, sync.canonical_block())
    tail = rendered.split(sync.END, 1)[1]
    for element in ("image-generation-content", "prompt", "port", "steps", "seed", "go", "outimg", "profiles", "gallery"):
        assert f'id="{element}"' in tail, f"Missing image cockpit content: {element}"
    assert rendered.count("if (window.__soAppShell) return") == 1
    assert "</main>" in tail and "</html>" in tail
    sync.validate_scripts(rendered)
