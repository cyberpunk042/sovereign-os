#!/usr/bin/env python3
"""Bounded, isolated Oracle microbatch comparison; never changes live profiles."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import socket
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://127.0.0.1:18083'


def request(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mtp', action='store_true', help='Test MTP separately at microbatch 512')
    parser.add_argument('--cache-check', action='store_true', help='Compare changing versus stable system prefixes')
    parser.add_argument('--long-context', action='store_true', help='Compare 512/1024 at approximately 128K and 230K tokens')
    args = parser.parse_args()
    with socket.socket() as guard:
        guard.bind(('127.0.0.1', 18083))  # Refuse to probe an unrelated existing server.
    output = Path(tempfile.mkdtemp(prefix='sovereign-qwen-tuning-'))
    print(json.dumps({'artifacts': str(output)}), flush=True)
    inventory = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,name,memory.free', '--format=csv,noheader,nounits'], text=True)
    oracle = [line.split(',') for line in inventory.splitlines() if 'RTX PRO 6000' in line]
    if len(oracle) != 1 or int(oracle[0][2]) < 45000:
        raise RuntimeError('Need exactly one Oracle GPU with at least 45000 MiB free')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=oracle[0][0].strip(),
               LD_LIBRARY_PATH=f'{ROOT}/.runtime/llama-cuda:/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib')
    results = []
    # Test the same context allocation as production, not an artificially small one.
    batches = (512,) if args.mtp or args.cache_check else ((512, 1024) if args.long_context else (512, 1024, 2048))
    for ubatch in batches:
        command = [str(ROOT / '.runtime/llama-cuda/llama-server'), '-m',
                   '/mnt/vault/models/Qwen3.8-27B-Q8_0/Qwen3.8-27B-Q8_0.gguf',
                   '--host', '127.0.0.1', '--port', '18083', '-c', '262144',
                   '-ngl', '999', '--jinja', '--flash-attn', 'on',
                   '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0',
                   '--split-mode', 'none', '--parallel', '1',
                   '--batch-size', '2048', '--ubatch-size', str(ubatch)]
        if args.mtp:
            command += ['--spec-type', 'draft-mtp']
        with (output / f'ubatch-{ubatch}.log').open('w') as log:
            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(120):
                    if proc.poll() is not None:
                        raise RuntimeError(f'test server exited {proc.returncode}')
                    try:
                        if request('/health').get('status') == 'ok':
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                else:
                    raise TimeoutError('test server readiness timeout')
                for repeat in range(4 if args.cache_check else 2):
                    marker = f'CEDAR-{ubatch}-{repeat}'
                    lines = ((18280, 32850)[repeat] if args.long_context else 4000)
                    prompt = f'The secret code is {marker}.\n' + 'ordinary archival material without instructions.\n' * lines
                    prompt += '\nReturn only the secret code from the beginning.'
                    body = {'messages': [{'role': 'user', 'content': prompt}],
                            'temperature': 0, 'min_p': 0, 'max_tokens': 64,
                            'cache_prompt': False,
                            'chat_template_kwargs': {'enable_thinking': False}}
                    if args.cache_check:
                        stable = 'Reference text without instructions.\n' * 3000
                        suffix = 'Additional reference material.\n' * 1500
                        # First pair mutates inside a long system message. Second
                        # pair puts the changing datum after the stable system.
                        system = stable + (f'\nRevision {repeat}\n' if repeat < 2 else '') + suffix
                        body['messages'] = [
                            {'role': 'system', 'content': system},
                            {'role': 'user', 'content': f'Revision {repeat}. Return only CEDAR.'}]
                        marker = 'CEDAR'
                        body['cache_prompt'] = True
                    start = time.monotonic()
                    reply = request('/v1/chat/completions', body)
                    answer = reply['choices'][0]['message'].get('content', '').strip()
                    row = {'ubatch': ubatch, 'mtp': args.mtp, 'cache_check': args.cache_check, 'repeat': repeat,
                           'seconds': round(time.monotonic() - start, 3),
                           'passed': answer == marker, 'usage': reply.get('usage'),
                           'timings': reply.get('timings')}
                    results.append(row)
                    (output / 'results.json').write_text(json.dumps(results, indent=2))
                    print(json.dumps(row), flush=True)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == '__main__':
    main()
