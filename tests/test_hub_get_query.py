"""Route matching must not discard backing API query parameters."""
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('route', ['panel', 'registry', 'exact'])
@pytest.mark.parametrize('query', ['', '?name=2026-10-10T111429Z-8188.png', '?name=a%2Fb&limit=2'])
def test_get_forwards_query_verbatim(route, query):
    source = Path(__file__).resolve().parents[1] / 'scripts/operator/build-configurator-api.py'
    tree = ast.parse(source.read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'do_GET')
    path = '/api/image-gen/artifact'
    namespace = {
        '_panel_prefixed': lambda p: (8150, path) if route == 'panel' else (None, None),
        '_route_and_path': lambda p: (8150, path) if route == 'registry' else (None, None),
        'DEV_GATEWAY_EXACT': {path: 8150},
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    handler = Mock()
    handler.path = path + query
    namespace['do_GET'](handler)
    handler._proxy.assert_called_once_with(8150, path + query)
