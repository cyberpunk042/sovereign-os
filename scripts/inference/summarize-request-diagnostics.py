#!/usr/bin/env python3
"""Summarize local request fingerprints without reading any conversation text."""
import argparse
import json
from pathlib import Path


def summarize(rows):
    pending, previous, output = {}, {}, []
    for row in rows:
        identity = (row.get('epoch'), row.get('route'))
        if row.get('event') == 'request':
            last = previous.get(identity)
            delta = {'previous_request_available': last is not None}
            if last:
                delta['tools_changed'] = last.get('tools') != row.get('tools')
                delta['settings_changed'] = last.get('settings_hash') != row.get('settings_hash')
                a, b = last.get('messages', []), row.get('messages', [])
                index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                delta['common_messages'] = index
                if index < len(a) and index < len(b):
                    delta['first_changed_role'] = b[index].get('role')
                    x, y = a[index].get('chunks', []), b[index].get('chunks', [])
                    if x and y:
                        delta['common_system_chunks_1024chars'] = next((i for i, (u, v) in enumerate(zip(x, y)) if u != v), min(len(x), len(y)))
            previous[identity] = row
            pending[row['id']] = delta
        elif row.get('event') == 'result':
            output.append({k: row.get(k) for k in ('at', 'route', 'ms', 'input', 'output', 'cacheRead', 'error')} | pending.pop(row['id'], {}))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path.home() / '.openclaw/diagnostics/requests.jsonl')
    args = parser.parse_args()
    with args.path.open() as source:
        rows = [json.loads(line) for line in source if line.strip()]
    print(json.dumps(summarize(rows), indent=2))
