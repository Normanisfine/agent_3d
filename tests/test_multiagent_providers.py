import io
import json
import subprocess

from agen3d.multiagent.contracts import ModelSpec
from agen3d.multiagent.providers import Provider


def test_http_protocol_and_cost(monkeypatch):
    monkeypatch.setenv("TEST_MODEL_KEY", "test-key")
    captured = {}

    def urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"status":"done"}'}}],
                                     "usage": {"cost": .002}, "model": "test"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    response = Provider().http(ModelSpec(backend="openrouter", model="test",
                                         api_key_env="TEST_MODEL_KEY", provider="pinned"),
                               "system", {}, [])
    assert response.actual_usd == .002
    assert captured["provider"] == {"require_parameters": True, "allow_fallbacks": False,
                                    "only": ["pinned"]}
    assert captured["max_tokens"] == 1800


def test_claude_requires_stream_output_and_uses_final_event(tmp_path, monkeypatch):
    captured = []

    def run(command, **kwargs):
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0,
            json.dumps({"type": "system"}) + "\n" + json.dumps({"type": "result",
                "result": '{"status":"done"}', "usage": {"output_tokens": 5},
                "total_cost_usd": .1}), "")

    monkeypatch.setattr("agen3d.multiagent.providers.run_process", run)
    reply = Provider().cli(ModelSpec(backend="claude"), "system", {}, [], tmp_path)
    assert captured[captured.index("--output-format") + 1] == "stream-json"
    assert captured[captured.index("--tools") + 1] == ""
    assert reply.actual_usd is None  # subscription equivalent != measured marginal charge
    assert json.loads(reply.text)["status"] == "done"


def test_codex_explicit_model_and_effort(tmp_path, monkeypatch):
    from pathlib import Path

    captured = []

    def run(command, **kwargs):
        captured.extend(command)
        Path(command[command.index("--output-last-message") + 1]).write_text('{"status":"pass"}')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr("agen3d.multiagent.providers.run_process", run)
    Provider().cli(ModelSpec(backend="codex", model="gpt-6-astra", reasoning_effort="medium"),
                   "system", {}, [], tmp_path)
    assert captured[captured.index("--model") + 1] == "gpt-6-astra"
    assert 'model_reasoning_effort="medium"' in captured
    assert captured[captured.index('model_reasoning_effort="medium"') - 1] == "-c"


def test_http_error_preserves_status_and_redacts_key(monkeypatch):
    import urllib.error
    import pytest
    from agen3d.multiagent.providers import ProviderHTTPError

    monkeypatch.setenv("TEST_MODEL_KEY", "secret-test-key")

    def urlopen(request, timeout):
        body = json.dumps({"error": {"message": "Rate limit secret-test-key",
                                    "metadata": {"raw": "private payload"}}}).encode()
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, io.BytesIO(body))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    with pytest.raises(ProviderHTTPError) as error:
        Provider().http(ModelSpec(backend="openrouter", model="test", api_key_env="TEST_MODEL_KEY"),
                        "system", {}, [])
    assert error.value.status == 429
    assert str(error.value) == "HTTP 429: Rate limit [redacted]"
    assert "private payload" not in str(error.value)


def test_http_enforces_response_schema_and_distinguishes_input(monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-key')
    captured={}
    def urlopen(request,timeout):
        captured.update(json.loads(request.data))
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"value":1}'}}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen',urlopen)
    schema={'title':'Result','type':'object','properties':{'value':{'type':'integer'}},
            'required':['value'],'additionalProperties':False}
    Provider().http(ModelSpec(backend='openrouter',model='test',api_key_env='TEST_MODEL_KEY'),
                    'system',{'schema':schema,'task':'Compute'},[])
    assert captured['response_format']['type']=='json_schema'
    assert captured['response_format']['json_schema']['schema']==schema
    assert captured['response_format']['json_schema']['strict'] is True
    content=captured['messages'][1]['content']
    assert content[0]['text'].startswith('INPUT CONTEXT ONLY')
    assert 'top-level keys are permitted: value' in content[-1]['text']


def test_text_mode_sampling_fence_and_usage(monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-key')
    captured={}
    raw='```json\n{"code":"pass"}\n```'
    def urlopen(request,timeout):
        captured.update(json.loads(request.data))
        return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':raw}}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'prompt_tokens_details':{'cached_tokens':3},'cost':.01}}).encode())
    monkeypatch.setattr('urllib.request.urlopen',urlopen)
    spec=ModelSpec(backend='openrouter',model='qwen/test',api_key_env='TEST_MODEL_KEY',response_mode='text',
                   temperature=.7,top_p=.8,top_k=20,presence_penalty=1.5,repetition_penalty=1.,seed=3407)
    reply=Provider().http(spec,'system',{},[])
    assert 'response_format' not in captured
    for name in ('temperature','top_p','top_k','presence_penalty','repetition_penalty','seed'):
        assert captured[name]==getattr(spec,name)
    assert reply.text=='{"code":"pass"}' and reply.raw_text==raw
    assert reply.usage['json_fence_removed']
    assert reply.usage['finish_reason']=='stop'
    assert reply.usage['input_tokens']==10 and reply.usage['output_tokens']==5
    assert reply.usage['cached_input_tokens']==3


def test_text_mode_never_extracts_json_from_prose(monkeypatch):
    monkeypatch.setenv('TEST_MODEL_KEY','test-key')
    raw='Here is a guess:\n```json\n{"code":"pass"}\n```'
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:io.BytesIO(json.dumps(
        {'choices':[{'message':{'content':raw}}]}).encode()))
    reply=Provider().http(ModelSpec(backend='openrouter',model='test',api_key_env='TEST_MODEL_KEY',response_mode='text'), 'system',{},[])
    assert reply.text==raw and not reply.usage['json_fence_removed']
