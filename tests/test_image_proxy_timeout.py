"""Exercise the actual hub proxy without starting host services."""
import ast
import http.client
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('method,path,extended', [
    ('POST', '/api/image-gen/generate', True),
    ('POST', '/api/image-gen/generate?source=cockpit', True),
    ('GET', '/api/image-gen/status', False),
    ('POST', '/api/control/execute', False),
])
def test_image_response_deadline(monkeypatch, method, path, extended):
    source = Path(__file__).resolve().parents[1] / 'scripts/operator/build-configurator-api.py'
    tree = ast.parse(source.read_text())
    proxy = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_proxy')
    namespace = {'json': json}
    exec(compile(ast.Module(body=[proxy], type_ignores=[]), str(source), 'exec'), namespace)
    connection = Mock()
    response = connection.getresponse.return_value
    response.getheader.side_effect = lambda key, default=None: {'Content-Length': '2', 'Content-Type': 'application/json'}.get(key, default)
    response.read.return_value = b'{}'
    response.status = 200
    def getresponse():
        if extended:
            connection.sock.settimeout.assert_called_once_with(930)
        else:
            connection.sock.settimeout.assert_not_called()
        return response
    connection.getresponse.side_effect = getresponse
    factory = Mock(return_value=connection)
    monkeypatch.setattr(http.client, 'HTTPConnection', factory)
    handler = Mock()
    namespace['_proxy'](handler, 8150, path, method, b'{}', 'application/json')
    factory.assert_called_once_with('127.0.0.1', 8150, timeout=30)
    handler._send.assert_called_once_with(200, b'{}', 'application/json')
    connection.close.assert_called_once()
