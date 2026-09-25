#!/usr/bin/env python3
"""Bounded dual-route OpenClaw read-tool workload, with transcript evidence.

No profile changes, external delivery or cloud fallback is requested. Writes only
generated fixtures and evidence under a new temporary run directory. CLI success
alone is not a pass: verify read calls, results, effective model and answer.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import secrets
import re
import sqlite3
import subprocess
import tempfile
import time


def evaluate(events, expected, route, meta):
    calls = []
    results = set()
    text = ''
    errors = 0
    for event in events:
        message = event.get('message', {})
        if message.get('role') == 'toolResult':
            if message.get('isError'):
                errors += 1
            else:
                results.add(message.get('toolCallId'))
        content = message.get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get('type') == 'toolCall':
                calls.append(block)
            if message.get('role') == 'assistant' and block.get('type') == 'text':
                text = block.get('text', '')
    reads = [c for c in calls if c.get('name') == 'read' and c.get('id') in results]
    paths = {str(c.get('arguments', {}).get('path', c.get('arguments', {}).get('file_path', '')))
             for c in reads}
    effective = meta.get('agentMeta', {}).get('model')
    passed = (all(str(p) in paths for p in expected['paths'])
              and all(code in text for code in expected['codes'])
              and re.search(r'(?<!\d)' + str(expected['total']) + r'(?!\d)',
                            re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', text)) is not None
              and not errors
              and all(c.get('name') == 'read' for c in calls)
              and effective == 'gpu-' + route
              and meta.get('executionTrace', {}).get('fallbackUsed') is False)
    return {'passed': passed, 'successful_reads': len(reads), 'tool_errors': errors,
            'unexpected_tools': [c.get('name') for c in calls if c.get('name') != 'read'],
            'effective_model': effective, 'final_answer': text}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 50:
        parser.error('rounds must be between 1 and 50')
    root = Path(tempfile.mkdtemp(prefix='sovereign-openclaw-qualification-'))
    print(json.dumps({'evidence_dir': str(root), 'rounds_per_card': args.rounds}), flush=True)
    db = Path.home() / '.openclaw/agents/main/agent/openclaw-agent.sqlite'

    def run(route):
        reports = []
        for iteration in range(args.rounds):
            case = root / f'{route}-{iteration}'
            case.mkdir()
            paths, codes, total = [], [], 0
            for index in range(3):
                path = case / f'ledger-{index}.txt'
                code = secrets.token_hex(6)
                amount = 100 + secrets.randbelow(800)
                lines = [f'Historical record {n}: archived, no current balance.' for n in range(220)]
                lines[20 + index * 70] = f'CURRENT: code={code}; amount={amount}'
                path.write_text('\n'.join(lines))
                paths.append(path)
                codes.append(code)
                total += amount
            expected = {'paths': paths, 'codes': codes, 'total': total}
            session = f'qualification-{root.name[-8:]}-{route}-{iteration}'
            prompt = ('Read each of these three local fixture files using only the read tool: '
                      + ', '.join(map(str, paths))
                      + '. Find the CURRENT record in each, return all three exact codes '
                      'and the sum of their amounts. Do not guess. Do not execute commands, '
                      'modify files, send messages, or use any other tool.')
            started = time.monotonic()
            try:
                result = subprocess.run(['openclaw', 'agent', '--agent', 'main',
                    '--session-id', session, '--model', 'sovereign/gpu-' + route,
                    '--message', prompt, '--timeout', '150', '--json'],
                    capture_output=True, text=True, timeout=180)
                reply = json.loads(result.stdout)
                meta = reply.get('result', {}).get('meta', {})
                with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
                    events = [json.loads(row[0]) for row in connection.execute(
                        'SELECT event_json FROM transcript_events WHERE session_id=? ORDER BY seq', (session,))]
                report = evaluate(events, expected, route, meta)
                report.update(usage=meta.get('agentMeta', {}).get('usage'),
                              compactions=sum(e.get('type') == 'compaction' for e in events))
            except Exception as error:
                report = {'passed': False, 'error_type': type(error).__name__}
            report.update(route=route, iteration=iteration, session=session,
                          seconds=round(time.monotonic() - started, 2))
            (case / 'result.json').write_text(json.dumps(report, indent=2))
            reports.append(report)
            print(json.dumps(report), flush=True)
            if not report['passed']:
                break  # diagnose before continuing a failing workload
        return reports

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(run, ('logic', 'oracle')))
    (root / 'summary.json').write_text(json.dumps(reports, indent=2))
    return 0 if all(len(rows) == args.rounds and all(r['passed'] for r in rows) for rows in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
