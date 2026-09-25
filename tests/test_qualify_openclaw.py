from pathlib import Path
import runpy

evaluate = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                             'scripts/inference/qualify-openclaw.py'))['evaluate']


def fixture():
    expected = {'paths': ['/tmp/a'], 'codes': ['code-a'], 'total': 123}
    meta = {'agentMeta': {'model': 'gpu-logic'}, 'executionTrace': {'fallbackUsed': False}}
    events = [
        {'message': {'role': 'assistant', 'content': [{'type': 'toolCall', 'name': 'read',
          'id': 'call-1', 'arguments': {'path': '/tmp/a'}}]}},
        {'message': {'role': 'toolResult', 'toolCallId': 'call-1', 'content': []}},
        {'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'code-a: total 123'}]}}
    ]
    return events, expected, meta


def test_real_read_and_correct_result_pass():
    events, expected, meta = fixture()
    assert evaluate(events, expected, 'logic', meta)['passed']


def test_correct_answer_without_execution_fails():
    events, expected, meta = fixture()
    assert not evaluate(events[-1:], expected, 'logic', meta)['passed']


def test_formatted_total_passes():
    events, expected, meta = fixture()
    expected['total'] = 1828
    events[-1]['message']['content'][0]['text'] = 'code-a: total 1,828'
    assert evaluate(events, expected, 'logic', meta)['passed']


def test_failed_tool_and_fallback_fail():
    events, expected, meta = fixture()
    events[1]['message']['isError'] = True
    assert not evaluate(events, expected, 'logic', meta)['passed']
    events[1]['message']['isError'] = False
    meta['executionTrace']['fallbackUsed'] = True
    assert not evaluate(events, expected, 'logic', meta)['passed']
