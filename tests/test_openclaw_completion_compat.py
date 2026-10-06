import copy
from pathlib import Path
import runpy
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = runpy.run_path(str(ROOT / 'scripts/inference/openclaw_completion_compat.py'))
ENSURE = runpy.run_path(str(ROOT / 'scripts/inference/sync-openclaw-models.py'))['_ensure_local_agent_completion']


def test_defaults_idempotence_and_overrides():
    cfg, changes = {}, []
    allocs = {tier: {'model': 'Qwen3.8-27B-Q8_0'} for tier in ('logic', 'oracle')}
    ENSURE(cfg, allocs, changes)
    defaults = cfg['agents']['defaults']
    assert defaults['models']['sovereign/gpu-oracle']['params']['extra_body']['reasoning_budget_tokens'] == 2048
    assert defaults['models']['sovereign/gpu-logic']['params']['extra_body']['reasoning_budget_tokens'] == 0
    assert defaults['subagents']['announceTimeoutMs'] == 600000
    before = copy.deepcopy(cfg)
    ENSURE(cfg, allocs, changes)
    assert cfg == before and len(changes) == 3
    defaults['subagents']['announceTimeoutMs'] = 900000
    body = defaults['models']['sovereign/gpu-oracle']['params']['extra_body']
    body.pop('reasoning_budget_tokens')
    body['thinking_budget_tokens'] = 1024
    ENSURE(cfg, allocs, [])
    assert defaults['subagents']['announceTimeoutMs'] == 900000
    assert body == {'thinking_budget_tokens': 1024}
    untouched = {}
    ENSURE(untouched, {'oracle': {'model': 'Other'}}, [])
    assert untouched == {}


def test_recovery_override_is_scoped_and_does_not_mutate_attempt():
    program = (ROOT / 'scripts/inference/openclaw-finalization-params.js').read_text() + '''
const assert = require('node:assert/strict');
const body = {temperature: 0.4, reasoning_budget_tokens: 2048,
 chat_template_kwargs: {enable_thinking: true, other: 'keep'}};
const attempt = {provider:'sovereign',modelId:'gpu-oracle',thinkLevel:'low',
 config:{agents:{defaults:{models:{'sovereign/gpu-oracle':{params:{extra_body:body}}}}}},
 streamParams:{topP:0.9,extra_body:{repeat_penalty:1.1}}};
const before = JSON.stringify(attempt);
const result = sovereignFinalizationParams(attempt);
assert.equal(result.thinkLevel,'off');
assert.equal(result.streamParams.extra_body.reasoning_budget_tokens,0);
assert.equal(result.streamParams.extra_body.chat_template_kwargs.enable_thinking,false);
assert.equal(result.streamParams.extra_body.chat_template_kwargs.other,'keep');
assert.equal(result.streamParams.extra_body.temperature,0.4);
assert.equal(result.streamParams.extra_body.repeat_penalty,1.1);
assert.equal(JSON.stringify(attempt),before);
assert.deepEqual(sovereignFinalizationParams({...attempt,provider:'other'}),{});
assert.deepEqual(sovereignFinalizationParams({...attempt,modelId:'other'}),{});
assert.deepEqual(sovereignFinalizationParams({...attempt,config:{}}),{});
'''
    subprocess.run(['node', '-e', program], check=True, capture_output=True, text=True)


def test_shape_gate_backup_idempotence_and_dry_run(tmp_path):
    path = tmp_path / 'builtin-openclaw-test.js'
    original = MOD['ANCHOR'] + '\n return {\n' + MOD['OLD'] + '\n };\n}\n'
    path.write_text(original)
    assert not MOD['patch_runtime'](tmp_path, True)
    assert path.read_text() == original
    assert MOD['patch_runtime'](tmp_path)
    assert not MOD['patch_runtime'](tmp_path)
    assert MOD['NEW'] in path.read_text()
    backup = path.with_suffix('.js.sovereign-finalization-v1.bak')
    assert backup.read_text() == original
    assert backup.stat().st_mode & 0o777 == 0o600
    assert 'disableTools: true' in path.read_text()
    path.write_text(original.replace('disableTools: true', 'disableTools: false'))
    with pytest.raises(RuntimeError, match='unsupported'):
        MOD['patch_runtime'](tmp_path)
    assert 'disableTools: false' in path.read_text()


def test_unknown_runtime_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match='missing'):
        MOD['patch_runtime'](tmp_path)


def test_installed_restricted_attempt_keeps_no_replay_guards():
    dist = Path.home() / '.npm-global/lib/node_modules/openclaw/dist'
    matches = [p for p in dist.glob('builtin-openclaw-*.js') if MOD['MARKER'] in p.read_text()]
    if len(matches) != 1:
        pytest.skip('patched runtime not installed')
    source = matches[0].read_text()
    start = source.index(MOD['ANCHOR'])
    factory = source[start:source.index('\n}', start)+2]
    program = (ROOT / 'scripts/inference/openclaw-finalization-params.js').read_text() + factory + '''
const assert = require('node:assert/strict');
const attempt = {provider:'sovereign',modelId:'gpu-oracle',thinkLevel:'low',
 config:{agents:{defaults:{models:{'sovereign/gpu-oracle':{params:{extra_body:{
 reasoning_budget_tokens:2048,chat_template_kwargs:{enable_thinking:true}}}}}}}}};
const r = buildRestrictedFinalizationAttempt(attempt);
assert.equal(r.operation,'settled-tool-finalization');
assert.equal(r.disableTools,true);
assert.equal(r.disableTrajectory,true);
assert.equal(r.skipPreparedUserTurnMessage,true);
assert.equal(r.suppressNextUserMessagePersistence,true);
assert.equal(r.thinkLevel,'off');
assert.equal(r.streamParams.extra_body.chat_template_kwargs.enable_thinking,false);
assert.equal(r.streamParams.extra_body.reasoning_budget_tokens,0);
assert.equal(attempt.thinkLevel,'low');
const other = buildRestrictedFinalizationAttempt({...attempt,provider:'another'});
assert.equal(other.thinkLevel,'low');
assert.equal(other.streamParams,undefined);
'''
    subprocess.run(['node', '-e', program], check=True, capture_output=True, text=True)
