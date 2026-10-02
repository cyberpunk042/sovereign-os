from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[1]
patch = runpy.run_path(str(ROOT / 'scripts/inference/install-request-diagnostics.py'))['patch']


def test_patch_is_narrow_and_idempotent():
    source = '''function createOpenAICompletionsExtraBodyWrapper(baseStreamFn, extraBody) {
        return streamWithPayloadPatch(underlying, model, context, options, (payloadObj) => {
            Object.assign(payloadObj, extraBody);
\t\t});
}
function nextFunction() { return 4; }
'''
    updated = patch(source)
    assert patch(updated) == updated
    assert 'Object.assign(payloadObj, extraBody);' in updated
    assert 'function nextFunction() { return 4; }' in updated
    assert 'tracedOptions' in updated


def test_metadata_excludes_contents_and_is_stable_within_process():
    module = (ROOT / 'scripts/inference/openclaw-request-diagnostics.mjs').as_uri()
    code = f'''
import assert from 'node:assert/strict';
import {{summarizePayload, traceManagedRequest}} from {module!r};
const p = {{messages:[{{role:'system',content:'PRIVATE_PROMPT_ABC'}}],
 tools:[{{function:{{name:'PRIVATE_TOOL',description:'PRIVATE_DESC'}}}}], api_key:'SECRET_TOKEN'}};
const a = summarizePayload(p), b = summarizePayload(p);
assert.deepEqual(a,b);
assert(!/PRIVATE|SECRET_TOKEN/.test(JSON.stringify(a)));
p.messages[0].content += 'changed';
assert.notEqual(a.messages[0].hash, summarizePayload(p).messages[0].hash);
const options = {{temperature:.7}}, stream = {{sentinel: true}};
assert.equal(traceManagedRequest({{provider:'unmanaged',id:'gpu-oracle'}},options,o=>{{assert.equal(o,options);return stream;}}),stream);
'''
    subprocess.run(['node', '--input-type=module', '-e', code], check=True)


def test_summary_distinguishes_prompt_and_tool_changes():
    summarize = runpy.run_path(str(ROOT / 'scripts/inference/summarize-request-diagnostics.py'))['summarize']
    first = {'event':'request', 'epoch':'a', 'route':'gpu-oracle', 'id':'1', 'tools':['x'],
             'settings_hash':'s', 'messages':[{'role':'system','hash':'a','chunks':['a','b']}]}
    second = first | {'id':'2', 'messages':[{'role':'system','hash':'b','chunks':['a','c']}]}
    result = summarize([first, second, {'event':'result','id':'2','route':'gpu-oracle','cacheRead':0}])[0]
    assert result['tools_changed'] is False
    assert result['first_changed_role'] == 'system'
    assert result['common_system_chunks_1024chars'] == 1
