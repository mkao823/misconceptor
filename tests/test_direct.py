from src.baselines import direct as D
from src.llm import LLMClient, MockTransport
from src.schema import SPECIAL_LABELS, label_set, load_taxonomy

CFG = {"default_model": "fake-model", "default_provider": "fake",
       "providers": {"fake": {"base_url": None, "api_key_env": "X", "api_key_required": False, "models": []}}}
ROW = {"id": "E10.Q07.A01", "question_id": "E10.Q07",
       "question": "How many comparisons to find an element in a BST?",
       "instructor_answer": "The height of the tree.", "student_answer": "n log n comparisons"}


def test_template_lists_ids_but_no_taxonomy_text():
    tax = load_taxonomy()
    tpl = D.load_template("direct_v1")
    msgs = D.render_messages(tpl, ROW, label_set(tax))
    assert msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    user = msgs[1]["content"]
    for item in tax["items"]:
        assert f"- {item['id']}\n" in user or user.endswith(f"- {item['id']}")
        assert item["description"].split(".")[0] not in user, "taxonomy descriptions must not leak into cond 1"
        for phrase in item.get("trigger_phrases") or []:
            assert f'"{phrase}"' not in user
    for sp in SPECIAL_LABELS:
        assert sp in user
    assert ROW["question"] in user and ROW["student_answer"] in user and "$" not in user
    assert len(tpl.sha256) == 64


def test_predict_row_with_mock_transport(tmp_path):
    transport = MockTransport('{"label": "BOsearchVsSort", "evidence": [{"source": "student_answer", '
                              '"span": "n log n"}], "confidence": 0.9}')
    client = LLMClient("fake-model", transport=transport, cache_dir=tmp_path, models_cfg=CFG)
    rec, err = D.predict_row(ROW, client, D.load_template(), label_set(), max_repairs=1)
    assert err is None and rec.label == "BOsearchVsSort" and rec.citation_valid
    assert rec.meta["attempts"] == 1 and rec.meta["cached"] is False and rec.meta["prompt_tokens"] == 10


def test_repair_round_trip_then_failure(tmp_path):
    replies = iter(["not json at all", '{"label": "Bogus", "evidence": [], "confidence": 0.5}'])
    transport = MockTransport(lambda _req: next(replies))
    client = LLMClient("fake-model", transport=transport, cache_dir=tmp_path, models_cfg=CFG)
    rec, err = D.predict_row(ROW, client, D.load_template(), label_set(), max_repairs=1)
    assert rec is None and err["stage"] == "validate" and "Bogus" in err["error"] and err["attempts"] == 2
    assert transport.calls[1]["messages"][-1]["role"] == "user" and "invalid" in transport.calls[1]["messages"][-1]["content"]
    assert err["usage"]["prompt_tokens"] == 20
