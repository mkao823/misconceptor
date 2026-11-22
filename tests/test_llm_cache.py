import json

import pytest

from src.llm import LLMClient, LLMError, MockTransport, make_cache_key

CFG = {"default_model": "fake-model", "default_provider": "fake",
       "providers": {"fake": {"base_url": "http://nowhere", "api_key_env": "X", "api_key_required": False,
                              "models": ["fake-model"]}}}
MSGS = [{"role": "user", "content": "hi"}]


def test_cache_round_trip(tmp_path):
    transport = MockTransport('{"label": "none", "evidence": [], "confidence": 0.5}',
                              prompt_tokens=7, completion_tokens=3)
    client = LLMClient("fake-model", transport=transport, cache_dir=tmp_path, models_cfg=CFG)

    r1 = client.chat(MSGS, temperature=0.0, seed=0, max_tokens=50)
    assert r1.cached is False and r1.text.startswith('{"label"')
    assert (r1.usage.prompt_tokens, r1.usage.completion_tokens, r1.usage.total_tokens) == (7, 3, 10)
    assert len(transport.calls) == 1
    assert transport.calls[0]["response_format"] == {"type": "json_object"}
    assert transport.calls[0]["seed"] == 0 and transport.calls[0]["max_tokens"] == 50

    r2 = client.chat(MSGS, temperature=0.0, seed=0, max_tokens=50)
    assert r2.cached is True and r2.text == r1.text and r2.cache_key == r1.cache_key
    assert len(transport.calls) == 1, "second identical call must not hit the transport"
    assert r2.usage.total_tokens == 10

    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1 and json.loads(files[0].read_text())["response"]["choices"][0]["message"]["content"] == r1.text

    # a fresh client over the same cache dir still hits the cache (survives process restarts)
    t2 = MockTransport("different")
    client2 = LLMClient("fake-model", transport=t2, cache_dir=tmp_path, models_cfg=CFG)
    assert client2.chat(MSGS, temperature=0.0, seed=0, max_tokens=50).text == r1.text and t2.calls == []

    stats = client.stats()
    assert stats["calls_uncached"] == 1 and stats["calls_cached"] == 1
    assert stats["tokens_uncached"]["total_tokens"] == 10 and stats["tokens_total"]["total_tokens"] == 20


def test_cache_key_covers_all_generation_parameters(tmp_path):
    transport = MockTransport("x")
    client = LLMClient("fake-model", transport=transport, cache_dir=tmp_path, models_cfg=CFG)
    client.chat(MSGS, temperature=0.0, seed=0, max_tokens=50)
    client.chat(MSGS, temperature=0.7, seed=0, max_tokens=50)
    client.chat(MSGS, temperature=0.0, seed=1, max_tokens=50)
    client.chat(MSGS, temperature=0.0, seed=0, max_tokens=51)
    client.chat(MSGS, temperature=0.0, seed=0, max_tokens=50, json_mode=False)
    client.chat([{"role": "user", "content": "hi!"}], temperature=0.0, seed=0, max_tokens=50)
    assert len(transport.calls) == 6
    keys = {make_cache_key("m", MSGS, 0.0, 0, 50, True), make_cache_key("m2", MSGS, 0.0, 0, 50, True)}
    assert len(keys) == 2


def test_use_cache_false_bypasses_disk(tmp_path):
    transport = MockTransport("x")
    client = LLMClient("fake-model", transport=transport, cache_dir=tmp_path, use_cache=False, models_cfg=CFG)
    client.chat(MSGS); client.chat(MSGS)
    assert len(transport.calls) == 2 and list(tmp_path.rglob("*.json")) == []


def test_transport_failure_raises_llm_error(tmp_path):
    def boom(_request):
        raise ConnectionError("refused")
    client = LLMClient("fake-model", transport=boom, cache_dir=tmp_path, models_cfg=CFG,
                       max_retries=1, retry_wait=0.0)
    with pytest.raises(LLMError, match="refused"):
        client.chat(MSGS)
