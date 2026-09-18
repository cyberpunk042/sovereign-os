import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / "scripts/inference/openclaw_context_compat.py"))
HELPER = ROOT / "scripts/inference/openclaw-context-accounting.js"


class ContextCompatibilityTests(unittest.TestCase):
    def test_installed_precheck_uses_measured_history_without_double_system(self):
        dist = Path.home() / ".npm-global/lib/node_modules/openclaw/dist"
        paths = [p for p in dist.glob("helpers-*.js") if MODULE["MARKER"] in p.read_text()]
        if len(paths) != 1:
            self.skipTest("patched local OpenClaw runtime not installed")
        program = '''
import {A as check} from MODULE;
import assert from 'node:assert/strict';
for (let cycle=0;cycle<20;cycle++) {
 const messages=[{role:'assistant',provider:'sovereign',api:'openai-completions',
 stopReason:'toolUse',usage:{input:75211,output:60},content:[]},
 {role:'toolResult',toolName:'read',content:[{type:'text',text:'x'.repeat(14996)}]}];
 const params={messages,systemPrompt:'x'.repeat(33053),prompt:'',
 contextTokenBudget:131072,reserveTokens:20000};
 const fits=check(params);
 assert.equal(fits.route,'fits');
 assert.equal(fits.pressureSource,'provider_context_usage');
 assert.ok(fits.estimatedPromptTokens<90000);
 messages[0].usage.input=125000;
 assert.notEqual(check(params).route,'fits'); // real pressure still guarded
}
'''.replace('MODULE', json.dumps(paths[0].as_uri()))
        result = subprocess.run(["node", "--input-type=module", "-e", program], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_measured_usage_and_bounded_progress(self):
        program = HELPER.read_text() + r'''
const assert = require('node:assert/strict');
const m = {role:'assistant',provider:'sovereign',api:'openai-completions',
 stopReason:'toolUse',usage:{input:75211,output:60,cacheRead:1000}};
assert.deepEqual(sovereignMeasuredBoundary(m, 4),
 {index:4,totalTokens:75271,includesSystemPrompt:true});
assert.equal(sovereignMeasuredBoundary({...m,provider:'other'},0),undefined);
assert.equal(sovereignMeasuredBoundary({...m,stopReason:'error'},0),undefined);
assert.equal(sovereignMeasuredBoundary({...m,usage:{input:NaN,output:0}},0),undefined);
assert.equal(sovereignMeasuredBoundary({...m,usage:{...m.usage,contextUsage:{state:'unavailable'}}},0),undefined);
const state={overflowCompactionAttempts:2};
const call=(id,path,error=false)=>({provider:'sovereign',state,attempt:{
 toolMetas:[{toolCallId:id,isError:error}],messagesSnapshot:[{role:'assistant',
 content:[{type:'toolCall',id,name:'read',arguments:{path}}]}]}});
sovereignRecoveryProgress(call('a','one'));
assert.equal(state.overflowCompactionAttempts,2); // no successful compaction yet
state.sovereignCompacted=true;
sovereignRecoveryProgress(call('b','one'));
assert.equal(state.overflowCompactionAttempts,2); // repeat with a new ID
state.sovereignCompacted=true;
sovereignRecoveryProgress(call('c','two',true));
assert.equal(state.overflowCompactionAttempts,2); // failed tool
for(let i=0;i<12;i++) {
 state.sovereignCompacted=true; state.overflowCompactionAttempts=2;
 sovereignRecoveryProgress(call('new'+i,'distinct'+i));
 assert.equal(state.overflowCompactionAttempts,i<8?0:2);
}
assert.equal(state.sovereignProgressResets,8);
console.log('measured accounting and bounded recovery: OK');
'''
        result = subprocess.run(["node", "-e", program], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_patch_is_shape_gated_idempotent_and_dry_run_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            helpers = dist / "helpers-test.js"
            embedded = dist / "embedded-agent-test.js"
            helpers.write_text('function resolveProviderContextBoundary(messages) {}\n'
                '\t\tconst contextUsage = message?.role === "assistant" ? message.usage?.contextUsage : void 0;\n'
                'estimateRenderedPromptTokens(params) + (boundary ? 0 : replay?.prefixTokens ?? 0)')
            embedded.write_text('async function recoverEmbeddedRunOverflow(input) {}\n'
                '\tconst preflightRecovery = input.attempt.preflightRecovery;\n'
                '\t\tif (compactResult.compacted) {')
            original = helpers.read_text()
            patch = MODULE["patch_runtime"]
            self.assertFalse(patch(dist, True, lambda _: None))
            self.assertEqual(helpers.read_text(), original)
            self.assertTrue(patch(dist, False, lambda _: None))
            self.assertFalse(patch(dist, False, lambda _: None))
            self.assertEqual(helpers.with_suffix('.js.sovereign-context-v1.bak').read_text(), original)
            embedded.write_text('async function recoverEmbeddedRunOverflow(input) {}')
            with self.assertRaises(RuntimeError):
                patch(dist, False, lambda _: None)


if __name__ == '__main__':
    unittest.main()
