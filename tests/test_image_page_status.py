"""Exercise the page's real status loader against HTTP/schema failures."""
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('ok,payload,expected', [
    (False, {'error': 'backing API on :8150 not reachable'}, 'Image status unavailable'),
    (True, {}, 'Image status unavailable'),
    (True, {'service': 'image-generation-api', 'active_profile': 'codernext-image-companion',
            'image_probes': [], 'ready_ports': [], 'image_profiles': []}, 'rendered'),
])
def test_status_loader(ok, payload, expected):
    html = (ROOT / 'webapp/image-generation/index.html').read_text()
    loader = html.split('  function load(){', 1)[1].split("  $('go').addEventListener", 1)[0]
    program = """
const elements = {};
function $(id) { return elements[id] || (elements[id] = {}); }
let STATUS = null;
function renderStatus(st) { $('banner').textContent = 'rendered'; }
function renderProfiles() {}
function renderGallery() {}
const fetch = async () => ({ok: OK, status: OK ? 200 : 502, json: async () => (PAYLOAD)});
function load(){LOADER
load();
setImmediate(() => {
  if (!$('banner').textContent.startsWith(EXPECTED)) throw Error(JSON.stringify(elements));
  if (EXPECTED !== 'rendered' && !$('go').disabled) throw Error('generation must be disabled');
});
""".replace('LOADER', loader).replace('PAYLOAD', json.dumps(payload)).replace('EXPECTED', json.dumps(expected)).replace('OK', json.dumps(ok))
    result = subprocess.run(['node', '-e', program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
