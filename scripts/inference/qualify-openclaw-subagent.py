#!/usr/bin/env python3
"""Opt-in bounded local parent/child read-only test; no external delivery.

Creates one retained test session and child plus private temporary evidence.
Passing requires an actual child read and a subsequent parent answer, not just
the CLI's accepted/yielded status. Never retries or replays a failed run.
"""
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tempfile
import time


def events(db, session):
    return [json.loads(row[0]) for row in db.execute(
        'SELECT event_json FROM transcript_events WHERE session_id=? ORDER BY seq', (session,))]


def inspect(messages):
    calls, text, errors, limits = [], [], 0, 0
    for event in messages:
        m = event.get('message', {})
        errors += int(m.get('isError', False) or m.get('stopReason') == 'error')
        limits += int(m.get('stopReason') == 'length')
        for block in m.get('content', []) if isinstance(m.get('content'), list) else []:
            if block.get('type') == 'toolCall':
                calls.append(block)
            if m.get('role') == 'assistant' and block.get('type') == 'text':
                text.append(block.get('text', ''))
    return calls, text, errors, limits


def main():
    root = Path(tempfile.mkdtemp(prefix='sovereign-subagent-qualification-'))
    token = secrets.token_hex(12)
    fixture = root / 'read-only-fixture.txt'
    fixture.write_text('Verification code: ' + token + '\n')
    fixture.chmod(0o600)
    session = 'subagent-qualification-' + secrets.token_hex(8)
    task = (f'Read {fixture} with the read tool exactly once and return its exact verification code. '
            'Do not run commands, write files, spawn agents, or call other tools.')
    prompt = ('This is a bounded sub-agent delivery qualification, not project work. '
              'Use sessions_spawn exactly once, with model sovereign/gpu-oracle, cleanup keep, '
              'runTimeoutSeconds 180 and this task: ' + task +
              ' Then use sessions_yield to await completion. Once the child completes, '
              'report its exact verification code. Do not read the fixture yourself, '
              'run commands, modify files, send external messages, or spawn a second child.')
    print(json.dumps({'evidence_dir': str(root), 'parent_session': session}), flush=True)
    started = time.monotonic()
    process = subprocess.Popen(['openclaw', 'agent', '--agent', 'main', '--session-id', session,
        '--model', 'sovereign/gpu-oracle', '--message', prompt, '--timeout', '480', '--json'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    db_path = Path.home() / '.openclaw/agents/main/agent/openclaw-agent.sqlite'
    report = {'passed': False}
    try:
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
            while time.monotonic() - started < 570:
                parent = events(db, session)
                pc, pt, pe, pl = inspect(parent)
                child_keys = []
                for e in parent:
                    m = e.get('message', {})
                    if m.get('role') == 'toolResult' and m.get('toolName') == 'sessions_spawn':
                        details = m.get('details', {})
                        if details.get('childSessionKey'):
                            child_keys.append(details['childSessionKey'])
                        for b in m.get('content', []):
                            if b.get('type') == 'text':
                                try:
                                    value = json.loads(b['text'])
                                    if value.get('childSessionKey'):
                                        child_keys.append(value['childSessionKey'])
                                except (ValueError, AttributeError):
                                    pass
                child_keys = list(dict.fromkeys(child_keys))
                children = []
                for key in child_keys:
                    row = db.execute('SELECT current_session_id FROM session_nodes WHERE session_key=?', (key,)).fetchone()
                    if row:
                        children.extend(events(db, row[0]))
                cc, ct, ce, cl = inspect(children)
                read_ok = any(c.get('name') == 'read' and
                    c.get('arguments', {}).get('path', c.get('arguments', {}).get('file_path')) == str(fixture) for c in cc)
                passed = (len(child_keys) == 1 and read_ok and any(token in t for t in ct)
                          and any(token in t for t in pt) and not(pe or pl or ce or cl)
                          and sum(c['name'] == 'sessions_spawn' for c in pc) == 1
                          and all(c['name'] in ('sessions_spawn', 'sessions_yield') for c in pc)
                          and all(c['name'] == 'read' for c in cc))
                report = {'passed': passed, 'elapsed_seconds': round(time.monotonic()-started, 2),
                          'parent_session': session, 'child_keys': child_keys,
                          'parent_tools': [c['name'] for c in pc], 'child_tools': [c['name'] for c in cc],
                          'errors': pe+ce, 'length_stops': pl+cl,
                          'child_returned_code': any(token in t for t in ct),
                          'parent_returned_code': any(token in t for t in pt)}
                if passed or pe or ce or pl or cl:
                    break
                time.sleep(3)
    finally:
        # Terminate only this test's CLI process; never kill the gateway/model.
        if process.poll() is None:
            process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        (root / 'cli-output.json').write_text(stdout)
        (root / 'cli-stderr.txt').write_text(stderr)
        (root / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
