#!/usr/bin/env python3
"""Bounded live Flash-Next retrieval probe; refuses the wrong resident model."""
import json
import argparse
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import time
import urllib.request


def request(path, body=None):
    req = urllib.request.Request('http://127.0.0.1:8083' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extended', action='store_true', help='Test approximately 128K and 230K on a 256K resident')
    args = parser.parse_args()
    props = request('/props')
    if 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S' not in props.get('model_path', ''):
        raise RuntimeError('Expected Flash-Next IQ3_S resident')
    slots = request('/slots')
    if any(slot.get('is_processing') for slot in slots):
        raise RuntimeError('Oracle busy; do not interrupt a user generation')
    limit = min(slot['n_ctx'] for slot in slots)
    if args.extended and limit < 262144:
        raise RuntimeError('Extended probe requires a 256K backend')
    output = Path(tempfile.mkdtemp(prefix='flash-next-context-'))
    print(json.dumps({'evidence_dir': str(output)}), flush=True)
    results, samples = [], []
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            raw = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.used', '--format=csv,noheader,nounits'], text=True)
            samples.extend(int(line.rsplit(',', 1)[1]) for line in raw.splitlines() if 'RTX PRO 6000' in line)
            stop.wait(1)
    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    try:
        for lines in ((18280, 32850) if args.extended else (4500, 8300)):
            codes = [secrets.token_hex(6) for _ in range(3)]
            filler = 'ordinary archival material without instructions.\n'
            prompt = (f'Beginning verification code: {codes[0]}\n' + filler * (lines//2)
                      + f'Middle verification code: {codes[1]}\n' + filler * (lines-lines//2)
                      + f'Ending verification code: {codes[2]}\nReturn the three verification codes, in order. No explanation.')
            count = len(request('/tokenize', {'content': prompt})['tokens'])
            if not 30000 <= count <= min(240000 if args.extended else 61000, limit - 4096):
                raise RuntimeError(f'Unexpected fixture token count {count}; refuse unbounded probe')
            body = {'model':'gpu-oracle','messages':[{'role':'user','content':prompt}],
                    'max_tokens':128,'temperature':0,'stream':False,
                    'chat_template_kwargs':{'enable_thinking':False},'reasoning_budget_tokens':0}
            started = time.monotonic()
            result = request('/v1/chat/completions', body)
            choice = result['choices'][0]
            answer = choice['message'].get('content') or ''
            passed = all(code in answer for code in codes) and choice['finish_reason'] == 'stop'
            row = {'passed':passed,'fixture_tokens':count,'seconds':round(time.monotonic()-started,2),
                   'usage':result.get('usage'),'timings':result.get('timings'),
                   'peak_oracle_mib':max(samples,default=0),'answer':answer}
            results.append(row)
            (output/'results.json').write_text(json.dumps(results,indent=2))
            print(json.dumps(row),flush=True)
            if not passed:
                return 1
    finally:
        stop.set()
        monitor.join(timeout=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
