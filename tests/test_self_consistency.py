"""Condition 4b (compute-matched self-consistency, docs/CRITIC_SPEC.md section 7) with a mock
client: the vote and its tie-breaks, the derivation of N, sampling, and the run script."""

import json

import pytest

from pipeline_helpers import ROW, Scripted, client_for, load_script, reply, run_script
from src import schema as S
from src.baselines import direct as D
from src.baselines import self_consistency as SC
from src.baselines import taxonomy_fewshot as TF
from src.retrieval import Retriever, load_corpus

GEN = {"temperature": 0.7, "seed": 0, "max_tokens": 2048, "json_mode": True, "max_repairs": 1}


@pytest.fixture(scope="module")
def setup():
    taxonomy = S.load_taxonomy()
    retriever = Retriever(load_corpus())
    template = D.load_template(TF.DEFAULT_TEMPLATE)
    prepared = TF.prepare_row(ROW, template, retriever, taxonomy, TF.load_fewshot(), k=4)
    return {"labels": S.label_set(taxonomy), "prepared": prepared}


# -- the vote --------------------------------------------------------------------------

def test_vote_majority_wins_whatever_the_confidences():
    r = SC.vote([("none", 0.2), ("BCwrite", 0.99), ("none", 0.3)])
    assert r.label == "none" and r.counts == {"none": 2, "BCwrite": 1} and r.tie_break == "none"
    assert r.tied_labels == ["none"] and r.share == pytest.approx(2 / 3)
    assert r.chosen == 2                                   # the highest-confidence sample that voted "none"


def test_vote_tie_goes_to_the_higher_mean_confidence():
    r = SC.vote([("none", 0.9), ("BCwrite", 0.8), ("BCwrite", 0.9), ("none", 0.6)])   # means 0.75 vs 0.85
    assert r.label == "BCwrite" and r.tie_break == "mean_confidence" and r.tied_labels == ["none", "BCwrite"]
    assert r.chosen == 2
    # a single high-confidence sample does not win a tie on its own: the mean decides
    r = SC.vote([("a", 1.0), ("a", 0.1), ("b", 0.6), ("b", 0.6), ("c", 0.99)])
    assert r.label == "b" and r.tie_break == "mean_confidence" and r.tied_labels == ["a", "b"]


def test_vote_tie_on_count_and_mean_goes_to_the_first_sample():
    r = SC.vote([("BCwrite", 0.7), ("none", 0.9), ("none", 0.5), ("BCwrite", 0.7)])    # 2-2, means 0.7 and 0.7
    assert r.label == "BCwrite" and r.tie_break == "first_sample" and r.chosen == 0
    r = SC.vote([("x", 0.5), ("y", 0.5), ("z", 0.5)])                                 # all different, all equal
    assert r.label == "x" and r.tie_break == "first_sample" and r.chosen == 0
    r = SC.vote([("x", 0.5), ("y", 0.6), ("z", 0.5)])                                 # all different: best mean
    assert r.label == "y" and r.tie_break == "mean_confidence" and r.chosen == 1
    # means that are equal up to float noise still count as tied: (0.1 + 0.2) / 2 versus 0.15
    r = SC.vote([("p", 0.15), ("q", 0.1), ("q", 0.2), ("p", 0.15)])
    assert r.label == "p" and r.tie_break == "first_sample"


def test_vote_representative_is_the_highest_confidence_majority_sample_earliest_on_a_tie():
    r = SC.vote([("none", 0.4), ("BCwrite", 0.95), ("none", 0.8), ("none", 0.8)])
    assert r.label == "none" and r.chosen == 2             # 0.8 twice: the earlier one
    assert SC.vote([("none", 0.5)]).chosen == 0
    with pytest.raises(ValueError):
        SC.vote([])


# -- N ---------------------------------------------------------------------------------

def test_n_is_the_ceiling_of_the_token_ratio():
    d = SC.derive_n_samples(17000.0, 5000.0)
    assert d["n_samples"] == 4 and d["n_before_floor"] == 4 and d["floor_applied"] is False
    assert d["token_ratio_cond4_to_single_call"] == 3.4
    assert d["budget_ratio_4b_to_4_planned"] == pytest.approx(20000 / 17000, abs=1e-4)
    assert (d["mean_tokens_per_row_cond4"], d["mean_tokens_single_cond3_call"]) == (17000.0, 5000.0)
    exact = SC.derive_n_samples(15000.0, 5000.0)             # a ratio of exactly 3 stays 3
    assert exact["n_samples"] == 3 and exact["floor_applied"] is False and exact["budget_ratio_4b_to_4_planned"] == 1.0
    noisy = SC.derive_n_samples(3 * 5448.8, 5448.8)          # float noise must not push it to 4
    assert noisy["n_samples"] == 3
    assert SC.derive_n_samples(15000.1, 5000.0)["n_samples"] == 4


def test_n_has_a_floor_of_three_and_the_floor_favours_the_baseline():
    d = SC.derive_n_samples(7000.0, 5000.0)                  # the Critic rarely triggered: ratio 1.4
    assert d["n_before_floor"] == 2 and d["n_samples"] == 3 and d["floor"] == 3 and d["floor_applied"] is True
    assert d["budget_ratio_4b_to_4_planned"] == pytest.approx(15000 / 7000, abs=1e-4) and d["budget_ratio_4b_to_4_planned"] > 1
    assert SC.derive_n_samples(5000.0, 5000.0)["n_samples"] == 3            # condition 4 that never called the Critic
    assert SC.derive_n_samples(7000.0, 5000.0, floor=1)["n_samples"] == 2
    for bad in ((0, 5000.0), (7000.0, 0), (None, 5000.0)):
        with pytest.raises(ValueError):
            SC.derive_n_samples(*bad)


def test_load_match_run_reads_a_condition_4_manifest_only(tmp_path):
    def write(run_id, manifest):
        (tmp_path / run_id).mkdir()
        (tmp_path / run_id / "manifest.json").write_text(json.dumps(manifest))

    write("c4", {"run_id": "c4", "condition": 4, "budget_reference": {
        "n_rows": 5, "mean_total_tokens_per_row": 9000.5, "mean_first_call_tokens_per_row": 5400.2}})
    m = SC.load_match_run("c4", tmp_path)
    assert (m["run_id"], m["mean_tokens_per_row"], m["mean_tokens_single_cond3_call"], m["n_rows"]) == ("c4", 9000.5, 5400.2, 5)
    assert SC.load_match_run(tmp_path / "c4")["run_id"] == "c4"            # a folder works as well as an id
    write("c3", {"run_id": "c3", "condition": 3})
    with pytest.raises(ValueError, match="not 4"):
        SC.load_match_run("c3", tmp_path)
    write("empty", {"run_id": "empty", "condition": 4, "budget_reference": {"n_rows": 0}})
    with pytest.raises(ValueError, match="budget_reference"):
        SC.load_match_run("empty", tmp_path)
    with pytest.raises(ValueError, match="no manifest"):
        SC.load_match_run("missing", tmp_path)


# -- one row ---------------------------------------------------------------------------

def test_samples_use_condition_3s_exact_prompt_at_temperature_07_with_distinct_seeds(setup):
    span = [{"source": "student_answer", "span": "two elements left"}]
    transport = Scripted([reply("BCwrite", span, 0.6), reply("none", (), 0.95), reply("BCwrite", span, 0.8),
                          reply("BCwrite", [{"source": "student_answer", "span": "two"}], 0.7), reply("none", (), 0.9)])
    rec, err = SC.predict_row(ROW, client_for(transport), setup["prepared"], setup["labels"], n_samples=5, **GEN)
    assert err is None and len(transport.calls) == 5
    for request in transport.calls:
        assert request["messages"] == setup["prepared"]["messages"]          # condition 3's prompt, unchanged
        assert request["temperature"] == 0.7 and request["max_tokens"] == 2048
    assert [request["seed"] for request in transport.calls] == [0, 1, 2, 3, 4] == SC.sample_seeds(0, 5)
    assert SC.sample_seeds(7, 3) == [7, 8, 9] and SC.sample_seeds(None, 2) == [0, 1]
    # the label is the majority; evidence and confidence come from its highest-confidence voter (sample 2)
    assert rec.label == "BCwrite" and rec.confidence == 0.8 and rec.student_spans == ["two elements left"]
    assert rec.meta["votes"] == {"BCwrite": 3, "none": 2} and rec.meta["vote_share"] == 0.6
    assert rec.meta["chosen_sample"] == 2 and rec.meta["tie_break"] == "none"
    assert (rec.meta["n_samples"], rec.meta["n_valid_samples"], rec.meta["n_calls"]) == (5, 5, 5)
    assert [s["label"] for s in rec.meta["samples"]] == ["BCwrite", "none", "BCwrite", "BCwrite", "none"]
    assert [s["seed"] for s in rec.meta["samples"]] == [0, 1, 2, 3, 4]
    # row tokens are the sum over the samples, and nothing escaped the client's own count
    client_total = sum(s["prompt_tokens"] + s["completion_tokens"] for s in rec.meta["samples"])
    assert rec.meta["prompt_tokens"] + rec.meta["completion_tokens"] == client_total
    assert rec.citation_valid and len(rec.meta["retrieved"]) == 4


def test_invalid_samples_are_dropped_from_the_vote_but_their_tokens_count(setup):
    transport = Scripted(["junk", "more junk",                       # sample 0: invalid even after its repair
                          reply("none", (), 0.9),                     # sample 1
                          "junk", reply("none", (), 0.4)])            # sample 2: valid after one repair
    client = client_for(transport)
    rec, err = SC.predict_row(ROW, client, setup["prepared"], setup["labels"], n_samples=3, **GEN)
    assert err is None and rec.label == "none" and rec.confidence == 0.9
    assert rec.meta["votes"] == {"none": 2} and rec.meta["n_valid_samples"] == 2 and rec.meta["chosen_sample"] == 1
    assert [s["valid"] for s in rec.meta["samples"]] == [False, True, True]
    assert [s["attempts"] for s in rec.meta["samples"]] == [2, 1, 2] and rec.meta["n_calls"] == 5
    assert rec.meta["prompt_tokens"] + rec.meta["completion_tokens"] == client.stats()["tokens_total"]["total_tokens"]
    assert [r["seed"] for r in transport.calls] == [0, 0, 1, 2, 2]     # a repair keeps its sample's seed

    client = client_for(Scripted(["junk"]))
    rec, err = SC.predict_row(ROW, client, setup["prepared"], setup["labels"], n_samples=3, **GEN)
    assert rec is None and err["stage"] == "all_samples_invalid" and err["n_calls"] == 6
    assert err["usage"]["prompt_tokens"] + err["usage"]["completion_tokens"] == client.stats()["tokens_total"]["total_tokens"]


# -- scripts/run_condition.py ----------------------------------------------------------

def load_run_condition():
    return load_script("run_condition")


def test_run_condition_4b_derives_n_from_the_matched_run_and_records_the_budget(tmp_path, monkeypatch, capsys):
    rc = load_run_condition()
    run_script(rc, monkeypatch, capsys, tmp_path, "--cond", "4", "--run-id", "c4")       # 2 calls per row, 30 tokens
    out = run_script(rc, monkeypatch, capsys, tmp_path, "--cond", "4b", "--match-run", "c4", "--run-id", "c4b")
    manifest = out["manifest"]
    assert manifest["condition"] == "4b" and manifest["condition_name"] == "self_consistency"
    assert manifest["prompt_template"]["sha256"] == D.load_template("taxonomy_fewshot_v1").sha256
    assert manifest["temperature"] == 0.7 and manifest["seed"] == 0
    sc = manifest["self_consistency"]
    # T4 = 30, T3 = 15: ceil(2.0) = 2, raised to the floor of 3, so 4b spends 45 tokens against 30
    assert (sc["mean_tokens_per_row_cond4"], sc["mean_tokens_single_cond3_call"]) == (30.0, 15.0)
    assert (sc["n_before_floor"], sc["n_samples"], sc["floor_applied"]) == (2, 3, True)
    assert sc["budget_ratio_4b_to_4_planned"] == 1.5 and sc["budget_ratio_4b_to_4_measured"] == 1.5
    assert sc["mean_total_tokens_per_row_4b"] == 45.0 and sc["seeds"] == [0, 1, 2]
    assert sc["match_run"]["run_id"] == "c4" and sc["match_run"]["differs_in"] == []
    assert manifest["per_row"] == [{"id": i, "prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45,
                                    "calls": 3, "error": False} for i in ("E05.Q04.S1", "E10.Q07.S1")]
    assert manifest["calls_per_row"]["mean_calls"] == 3.0 and manifest["calls"] == {"uncached": 6, "cached": 0}
    for p in out["predictions"]:
        assert p["meta"]["votes"] == {"insufficient_evidence": 3} and len(p["meta"]["samples"]) == 3
        assert "trace" not in p

    # a run that is not condition 4 cannot be matched
    run_script(rc, monkeypatch, capsys, tmp_path, "--cond", "3", "--run-id", "c3")
    monkeypatch.setattr("sys.argv", ["run_condition.py", "--mock", "--no-cache", "--sheet", str(tmp_path / "sheet.csv"),
                                     "--out-root", str(tmp_path), "--cond", "4b", "--match-run", "c3"])
    with pytest.raises(SystemExit, match="not 4"):
        rc.main()


def test_models_yaml_no_longer_has_a_todo_for_n_samples():
    from src.config import load_config
    sc = load_config("models")["self_consistency"]
    assert sc["n_samples"] == "from_match_run" and sc["min_samples"] == 3 and sc["temperature"] == 0.7
