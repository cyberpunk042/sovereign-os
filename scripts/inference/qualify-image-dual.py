#!/usr/bin/env python3
"""Bounded benign native-image smoke probes; persists evidence, not readiness."""
import base64
import argparse
import json
from pathlib import Path
import tempfile
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--steps', type=int, default=2, choices=range(1, 51))
parser.add_argument('--size', type=int, default=512, choices=(512, 1024))
parser.add_argument('--model', choices=('qwen', 'flux', 'both'), default='both')
args = parser.parse_args()
out = Path(tempfile.mkdtemp(prefix='sovereign-image-qualification-'))
print(f'Evidence: {out}', flush=True)
results = []
for name, port in [('qwen', 8188), ('flux', 8189)]:
    if args.model not in ('both', name):
        continue
    extra = json.dumps({'seed': 42, 'sample_params': {'sample_steps': args.steps}})
    body = json.dumps({'prompt': 'A red ceramic teapot on a white table, studio photograph.'
                       + '<sd_cpp_extra_args>' + extra + '</sd_cpp_extra_args>',
                       'size': f'{args.size}x{args.size}', 'n': 1}).encode()
    started = time.monotonic()
    request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/images/generations',
                                    data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            data = json.load(response)
        image = base64.b64decode(data['data'][0]['b64_json'], validate=True)
        if not image.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Response is not a PNG')
        (out / f'{name}.png').write_bytes(image)
        result = {'model': name, 'passed': True, 'steps': args.steps, 'size': args.size,
                  'qualification': 'PNG transport only; visual quality requires inspection', 'seconds': time.monotonic() - started,
                  'bytes': len(image), 'image': str(out / f'{name}.png')}
    except Exception as exc:
        result = {'model': name, 'passed': False, 'seconds': time.monotonic() - started,
                  'error': str(exc)}
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(result), flush=True)
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
