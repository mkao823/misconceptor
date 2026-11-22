"""Condition 4 (Critic-driven re-retrieval, docs/CRITIC_SPEC.md) with a mock client: stop rules,
chunk exclusion, token accounting, the Critic prompt and verdict, and the run script."""

import json
import re

import pytest

from pipeline_helpers import ROW, SETTINGS, Scripted, client_for, load_script, reply, run_script, verdict
from src import schema as S
from src.baselines import direct as D
from src.baselines import taxonomy_fewshot as TF
from src.pipeline import critic, loop
from src.retrieval import Retriever, load_corpus

INSUFFICIENT_1 = verdict(False, "whether a base case of two elements alone is accepted in this course",
                         "merge sort base case size 2 acceptable")
INSUFFICIENT_2 = verdict(False, "what the running time of merge sort is, to rule out a running-time answer",
                         "merge sort cost n log n best average worst case")


@pytest.fixture(scope="module")
def ctx():
    taxonomy = S.load_taxonomy()
    return loop.Context(template=D.load_template(loop.DEFAULT_TEMPLATE),
                        critic_template=D.load_template(loop.DEFAULT_CRITIC_TEMPLATE),
                        labels=S.label_set(taxonomy), retriever=Retriever(load_corpus()),
                        taxonomy=taxonomy, fewshot=TF.load_fewshot())


def run(ctx, diagnoses, verdicts=(), **kwargs):
    transport = Scripted(diagnoses, verdicts)
    rec, err, trace = loop.run_row(ROW, client_for(transport), ctx, **{**SETTINGS, **kwargs})
    return rec, err, trace, transport


def shown_ids(trace) -> list[list[str]]:
    return [r["chunk_ids_shown"] for r in trace["rounds"]]


# -- the first pass is condition 3 ---------------------------------------------------

def test_first_pass_is_condition_3_byte_for_byte(ctx, tmp_path):
    prepared = TF.prepare_row(ROW, ctx.template, ctx.retriever, ctx.taxonomy, ctx.fewshot, k=4)
    cond3_transport = Scripted([reply("none")])
    cond3, err = TF.predict_row(ROW, client_for(cond3_transport, tmp_path), ctx.template, ctx.labels,
                                ctx.retriever, ctx.taxonomy, ctx.fewshot, k=4, **SETTINGS)
    assert err is None

    # same cache directory, fresh client: the first pass of condition 4 is served from condition 3's entry
    transport = Scripted([reply("BCwrite")], [verdict(True)])       # a live diagnosis would say BCwrite
    rec, err, trace = loop.run_row(ROW, client_for(transport, tmp_path), ctx, k=4, **SETTINGS)
    assert err is None and transport.kinds == ["critic"]            # no diagnosis call reached the transport
    assert trace["calls"][0] == {"round": 0, "role": "diagnosis", "attempt": 1, "cached": True,
                                 "prompt_tokens": cond3.meta["prompt_tokens"],
                                 "completion_tokens": cond3.meta["completion_tokens"],
                                 "total_tokens": cond3.meta["prompt_tokens"] + cond3.meta["completion_tokens"]}
    assert rec.label == cond3.label == "none" and rec.meta["cache_key"] == cond3.meta["cache_key"]
    assert [h["id"] for h in rec.meta["retrieved"]] == [h["id"] for h in cond3.meta["retrieved"]]
    assert rec.meta["withheld_chunk_ids"] == cond3.meta["withheld_chunk_ids"] == ["ia.E05.Q04"]

    # and without any cache the request itself is identical: messages, temperature, seed
    rec, err, trace, transport = run(ctx, [reply("none")], [verdict(True)])
    first = transport.calls[0]
    assert first["messages"] == prepared["messages"] == cond3_transport.calls[0]["messages"]
    assert (first["temperature"], first["seed"], first["max_tokens"]) == (0.0, 0, 2048)
    assert first["response_format"] == {"type": "json_object"}


def test_max_rounds_zero_is_condition_3_and_never_calls_the_critic(ctx):
    rec, err, trace, transport = run(ctx, [reply("none")], max_rounds=0)
    assert err is None and transport.kinds == ["diagnosis"]
    assert trace["stop_reason"] == "round_limit" and trace["n_calls"] == 1 and trace["n_refinements"] == 0
    assert trace["rounds"][0]["critic"] is None and rec.meta["n_calls"] == 1


# -- stop rules ------------------------------------------------------------------------

def test_stops_when_the_critic_says_sufficient(ctx):
    evidence = [{"source": "student_answer", "span": "two elements left"}]
    rec, err, trace, transport = run(ctx, [reply("BCwrite", evidence, 0.6)], [verdict(True)])
    assert err is None and transport.kinds == ["diagnosis", "critic"]
    assert trace["stop_reason"] == "sufficient" and trace["n_refinements"] == 0 and trace["n_calls"] == 2
    assert trace["critic_triggered"] is False and len(trace["rounds"]) == 1
    round0 = trace["rounds"][0]
    assert round0["query_source"] == "row" and ROW["student_answer"].strip() in round0["query"]
    assert round0["critic"] == {"sufficient": True, "missing": "", "query": "", "attempts": 1}
    assert round0["draft"]["label"] == "BCwrite" and round0["calls"] == 2
    assert len(round0["chunk_ids_shown"]) == 4 and round0["new_chunk_ids"] == round0["chunk_ids_shown"]
    # the output is the first-pass record, untouched
    assert (rec.label, rec.confidence, rec.student_spans) == ("BCwrite", 0.6, ["two elements left"])
    assert rec.meta["stop_reason"] == "sufficient" and rec.meta["first_pass_label"] == "BCwrite"


def test_stops_at_the_round_limit_without_a_further_critic_call(ctx):
    drafts = [reply("BCwrite", [{"source": "student_answer", "span": "two elements"}]),
              reply("other_error", [{"source": "student_answer", "span": "two"}])]
    verdicts = [INSUFFICIENT_1, INSUFFICIENT_2, verdict(True)]
    # a first run tells us which chunk only round 2 brings in; the real run quotes from it
    _, _, probe, _ = run(ctx, drafts + [reply("none")], verdicts)
    quote = ctx.retriever.corpus.get(probe["rounds"][2]["new_chunk_ids"][-1]).text.split(". ")[0]
    final = reply("none", [{"source": "retrieved", "span": quote}], 0.8)
    rec, err, trace, transport = run(ctx, drafts + [final], verdicts)
    assert err is None
    assert transport.kinds == ["diagnosis", "critic", "diagnosis", "critic", "diagnosis"]   # no third Critic call
    assert trace["stop_reason"] == "round_limit" and trace["n_refinements"] == 2 and trace["n_calls"] == 5
    assert trace["critic_triggered"] is True
    rounds = trace["rounds"]
    assert [r["round"] for r in rounds] == [0, 1, 2]
    assert [r["query_source"] for r in rounds] == ["row", "critic", "critic"]
    assert rounds[1]["query"] == "merge sort base case size 2 acceptable"
    assert rounds[2]["query"] == "merge sort cost n log n best average worst case"
    assert [len(ids) for ids in shown_ids(trace)] == [4, 8, 12]
    assert [r["draft"]["label"] for r in rounds] == ["BCwrite", "other_error", "none"]
    assert rounds[0]["critic"]["sufficient"] is False and rounds[1]["critic"]["sufficient"] is False
    assert rounds[2]["critic"] is None                       # the last draft is not judged
    # the final record is the last re-diagnosis, and its spans are checked against ALL chunks shown
    assert rec.label == "none" and rec.meta["first_pass_label"] == "BCwrite" and trace["final_label"] == "none"
    assert rec.citation_valid and rec.sources_checked == ["student_answer", "retrieved", "taxonomy"]
    assert [h["round"] for h in rec.meta["retrieved"]] == [0] * 4 + [1] * 4 + [2] * 4
    assert any(quote in ctx.retriever.corpus.get(c).text for c in rounds[2]["new_chunk_ids"])
    assert not any(quote in ctx.retriever.corpus.get(c).text for c in rounds[1]["chunk_ids_shown"])
    # the re-diagnosis prompt is condition 3's template with the accumulated chunks, in order, and nothing else
    last_user = transport.calls[4]["messages"][1]["content"]
    positions = [last_user.index(f"[{c}]") for c in rounds[2]["chunk_ids_shown"]]
    assert positions == sorted(positions)
    assert "Draft diagnosis" not in last_user and "whether a base case of two elements" not in last_user
    first_user = transport.calls[0]["messages"][1]["content"]
    assert last_user.split("Course material retrieved")[0] == first_user.split("Course material retrieved")[0]

    one, _, trace1, transport1 = run(ctx, [reply("none")], [INSUFFICIENT_1], max_rounds=1)
    assert transport1.kinds == ["diagnosis", "critic", "diagnosis"]
    assert trace1["stop_reason"] == "round_limit" and trace1["n_refinements"] == 1


def test_stops_when_the_requery_returns_no_new_chunks(ctx):
    nothing = verdict(False, "something the corpus does not hold", "zzzqqq xyzzy")
    rec, err, trace, transport = run(ctx, [reply("none")], [nothing])
    assert err is None and transport.kinds == ["diagnosis", "critic"]      # no re-diagnosis
    assert trace["stop_reason"] == "no_new_chunks" and trace["n_refinements"] == 0 and trace["n_calls"] == 2
    assert trace["critic_triggered"] is True
    empty = trace["rounds"][1]
    assert empty["query"] == "zzzqqq xyzzy" and empty["query_source"] == "critic"
    assert empty["new_chunk_ids"] == [] and empty["draft"] is None and empty["critic"] is None
    assert empty["chunk_ids_shown"] == trace["rounds"][0]["chunk_ids_shown"]
    assert empty["calls"] == 0 and empty["tokens"]["total_tokens"] == 0
    assert rec.label == "none" and rec.meta["stop_reason"] == "no_new_chunks"


def test_stops_when_the_corpus_is_exhausted(tmp_path):
    sections = "\n\n".join(f"## Topic {i}\n\nRecursion note number {i} about base cases and merge sort."
                           for i in range(1, 6))
    (tmp_path / "notes.md").write_text(f"---\nsource: tiny\ntitle: Tiny notes\n---\n\n# Tiny\n\n{sections}\n",
                                       encoding="utf-8")
    corpus = load_corpus(tmp_path)
    assert len(corpus) == 5
    taxonomy = S.load_taxonomy()
    tiny = loop.Context(template=D.load_template(loop.DEFAULT_TEMPLATE),
                        critic_template=D.load_template(loop.DEFAULT_CRITIC_TEMPLATE),
                        labels=S.label_set(taxonomy), retriever=Retriever(corpus), taxonomy=taxonomy,
                        fewshot=TF.load_fewshot())
    more = verdict(False, "more about recursion", "recursion base cases merge sort")
    transport = Scripted([reply("none")], [more])
    rec, err, trace = loop.run_row(ROW, client_for(transport), tiny, k=4, max_rounds=5, **SETTINGS)
    assert transport.kinds == ["diagnosis", "critic", "diagnosis", "critic"]
    assert trace["stop_reason"] == "no_new_chunks" and trace["n_refinements"] == 1
    assert [len(ids) for ids in shown_ids(trace)] == [4, 5, 5]
    assert sorted(trace["rounds"][-1]["chunk_ids_shown"]) == sorted(corpus.ids())


def test_critic_error_stops_the_loop_and_keeps_the_draft(ctx):
    rec, err, trace, transport = run(ctx, [reply("none")], ["not json at all", '{"sufficient": "maybe"}'])
    assert err is None and transport.kinds == ["diagnosis", "critic", "critic"]      # one repair round-trip
    assert trace["stop_reason"] == "critic_error" and trace["critic_triggered"] is False
    assert trace["rounds"][0]["critic"]["sufficient"] is None and trace["rounds"][0]["critic"]["attempts"] == 2
    assert "sufficient must be true or false" in trace["rounds"][0]["critic"]["error"]
    assert rec.label == "none" and rec.meta["n_calls"] == 3


def test_rediagnosis_error_keeps_the_previous_valid_draft(ctx):
    rec, err, trace, transport = run(ctx, [reply("BCwrite", [{"source": "student_answer", "span": "two elements"}]),
                                           "garbage", "still garbage"], [INSUFFICIENT_1])
    assert err is None and transport.kinds == ["diagnosis", "critic", "diagnosis", "diagnosis"]
    assert trace["stop_reason"] == "rediagnosis_error" and trace["n_refinements"] == 0
    assert trace["rounds"][1]["draft"] is None and trace["rounds"][1]["draft_error"]["stage"] == "parse"
    assert rec.label == "BCwrite" and len(rec.meta["retrieved"]) == 4      # the draft that stands saw 4 chunks
    assert rec.meta["n_calls"] == 4 == trace["n_calls"]


def test_first_pass_error_goes_to_errors_without_a_critic_call(ctx):
    rec, err, trace, transport = run(ctx, ["nope", "nope again"], [verdict(True)])
    assert rec is None and transport.kinds == ["diagnosis", "diagnosis"]
    assert err["stage"] == "parse" and err["id"] == ROW["id"] and err["n_calls"] == 2
    assert trace["stop_reason"] == "first_pass_error" and err["trace"] is trace
    assert err["usage"]["prompt_tokens"] + err["usage"]["completion_tokens"] == trace["tokens"]["total_tokens"]


# -- exclusion -------------------------------------------------------------------------

class SpyRetriever:
    """Delegates to a Retriever and records every retrieve() call."""

    def __init__(self, inner):
        self.inner, self.corpus, self.queries = inner, inner.corpus, []

    def retrieve(self, query, k=4, exclude=()):
        exclude = list(exclude)
        hits = self.inner.retrieve(query, k, exclude)
        self.queries.append({"query": query, "k": k, "exclude": exclude, "ids": [h.chunk.id for h in hits]})
        return hits


def test_excluded_chunks_are_never_reshown(ctx):
    spy = SpyRetriever(ctx.retriever)
    spied = loop.Context(template=ctx.template, critic_template=ctx.critic_template, labels=ctx.labels,
                         retriever=spy, taxonomy=ctx.taxonomy, fewshot=ctx.fewshot)
    # both queries aim straight at chunks that must not come back: one already shown, one excluded for
    # the run, and the row's own instructor answer
    again = verdict(False, "the base case of merge sort", ROW["question"] + " " + ROW["instructor_answer"])
    converge = verdict(False, "convergence", "convergence base case step over zero odd never reached")
    transport = Scripted([reply("none")], [again, converge])
    rec, err, trace = loop.run_row(ROW, client_for(transport), spied, k=4, exclude=["rec.convergence"], **SETTINGS)
    assert err is None and trace["stop_reason"] == "round_limit"
    final = trace["rounds"][-1]["chunk_ids_shown"]
    assert len(final) == 12 == len(set(final))                       # no chunk is shown twice
    assert "rec.convergence" not in final and "ia.E05.Q04" not in final
    assert trace["withheld_chunk_ids"] == ["rec.convergence", "ia.E05.Q04"]
    seen: list[str] = []
    for r in trace["rounds"]:
        assert not set(r["new_chunk_ids"]) & set(seen)               # each round only adds unseen chunks
        seen += r["new_chunk_ids"]
        assert r["chunk_ids_shown"] == seen
    # every re-query excluded everything shown before it, the run-level exclusion and the own reference
    first, second, third = spy.queries
    assert set(first["exclude"]) == {"rec.convergence", "ia.E05.Q04"}
    assert set(second["exclude"]) == {"rec.convergence", "ia.E05.Q04", *trace["rounds"][0]["chunk_ids_shown"]}
    assert set(third["exclude"]) == {"rec.convergence", "ia.E05.Q04", *trace["rounds"][1]["chunk_ids_shown"]}
    assert second["query"] == ROW["question"] + " " + ROW["instructor_answer"] and second["k"] == 4
    # without the exclusions the same queries would have returned exactly those chunks
    assert "rec.merge-sort-base-case" in trace["rounds"][0]["chunk_ids_shown"]
    assert ctx.retriever.retrieve(second["query"], 4)[0].chunk.id in ("rec.merge-sort-base-case", "ia.E05.Q04")
    assert "rec.convergence" in [h.chunk.id for h in ctx.retriever.retrieve(third["query"], 4)]
    # the chunks shown to the model are the chunks in the trace
    for request, r in zip([c for c, kind in zip(transport.calls, transport.kinds) if kind == "diagnosis"],
                          trace["rounds"]):
        user = request["messages"][1]["content"]
        assert re.findall(r"^\[((?:rec|ana|ia)\.[^\]]+)\]", user, re.MULTILINE) == r["chunk_ids_shown"]


def test_first_pass_only_exclusion_and_forcing(ctx):
    target = "rec.merge-sort-base-case"
    # withheld from the first pass only: the re-query may bring it back (the positive control relies on this)
    rec, err, trace, _ = run(ctx, [reply("none")], [INSUFFICIENT_1], first_pass_exclude=[target], max_rounds=1)
    assert target not in trace["rounds"][0]["chunk_ids_shown"] and target in trace["rounds"][1]["new_chunk_ids"]
    assert trace["first_pass_withheld_chunk_ids"] == [target] and trace["withheld_chunk_ids"] == ["ia.E05.Q04"]
    # forced in: present even when it would not be retrieved, k unchanged, own reference still withheld
    hits, withheld, first_only = loop.first_pass_retrieval(ROW, ctx.retriever, k=4, first_pass_force=["ia.E10.Q02"])
    ids = [h.chunk.id for h in hits]
    natural = [h.chunk.id for h in ctx.retriever.retrieve(loop.build_query(ROW), 4, ["ia.E05.Q04"])]
    assert "ia.E10.Q02" not in natural and "ia.E10.Q02" in ids and len(ids) == 4
    assert set(ids) - {"ia.E10.Q02"} == set(natural[:3]) and [h.rank for h in hits] == [1, 2, 3, 4]
    assert withheld == ["ia.E05.Q04"] and first_only == []
    same, _, _ = loop.first_pass_retrieval(ROW, ctx.retriever, k=4, first_pass_force=[natural[1]])
    assert [h.chunk.id for h in same] == natural                      # forcing a chunk already there changes nothing
    with pytest.raises(ValueError, match="withheld"):
        loop.first_pass_retrieval(ROW, ctx.retriever, k=4, first_pass_force=["ia.E05.Q04"])


# -- tokens ----------------------------------------------------------------------------

def test_token_totals_equal_the_sum_over_every_call_including_critic_calls_and_repairs(ctx):
    transport = Scripted(["broken first pass", reply("none"), reply("none")],
                         ["broken verdict", INSUFFICIENT_1, verdict(True)])
    client = client_for(transport)
    rec, err, trace = loop.run_row(ROW, client, ctx, **SETTINGS)
    # diagnosis, its repair, Critic, its repair, re-diagnosis, Critic
    assert transport.kinds == ["diagnosis", "diagnosis", "critic", "critic", "diagnosis", "critic"]
    assert [(c["round"], c["role"], c["attempt"]) for c in trace["calls"]] == [
        (0, "diagnosis", 1), (0, "diagnosis", 2), (0, "critic", 1), (0, "critic", 2), (1, "diagnosis", 1),
        (1, "critic", 1)]
    assert trace["stop_reason"] == "sufficient" and trace["n_refinements"] == 1
    calls = trace["calls"]
    prompt = sum(c["prompt_tokens"] for c in calls)
    completion = sum(c["completion_tokens"] for c in calls)
    assert len({c["total_tokens"] for c in calls}) == 6                    # the mock gives every call its own usage
    assert trace["tokens"] == {"prompt_tokens": prompt, "completion_tokens": completion,
                               "total_tokens": prompt + completion}
    assert (rec.meta["prompt_tokens"], rec.meta["completion_tokens"]) == (prompt, completion)
    assert rec.meta["n_calls"] == trace["n_calls"] == len(calls) == len(transport.calls) == 6
    assert sum(r["tokens"]["total_tokens"] for r in trace["rounds"]) == prompt + completion
    assert [r["calls"] for r in trace["rounds"]] == [4, 2]
    assert client.stats()["tokens_total"]["total_tokens"] == prompt + completion       # nothing escaped the count
    assert trace["first_call_tokens"] == calls[0]["total_tokens"]
    assert all(c["total_tokens"] == c["prompt_tokens"] + c["completion_tokens"] for c in calls)


# -- the Critic ------------------------------------------------------------------------

def test_critic_prompt_shows_what_the_spec_says_and_nothing_else(ctx):
    evidence = [{"source": "student_answer", "span": "two elements left"}]
    rec, err, trace, transport = run(ctx, [reply("BCwrite", evidence, 0.7)], [verdict(True)])
    messages = transport.calls[1]["messages"]
    system, user = messages[0]["content"], messages[1]["content"]
    assert "JSON" in system and "do not change the diagnosis" in system
    order = ["Exam question:\n" + ROW["question"], "Instructor's reference answer:\n" + ROW["instructor_answer"],
             "Course material shown so far", "Student's answer:\n" + ROW["student_answer"].strip(),
             "Draft diagnosis", '"label": "BCwrite"', "Meaning of the draft label:\n- BCwrite (recursion):",
             '"sufficient"']
    positions = [user.index(s) for s in order]
    assert positions == sorted(positions)
    for cid in trace["rounds"][0]["chunk_ids_shown"]:                  # every chunk shown so far, id and text
        assert f"[{cid}]" in user and ctx.retriever.corpus.get(cid).text in user
    assert json.dumps({"label": "BCwrite", "evidence": evidence, "confidence": 0.7}) in user
    # not the rest of the taxonomy, not the few-shot examples
    others = [i for i in ctx.taxonomy["items"] if i["id"] != "BCwrite"]
    assert not any(S.normalize_ws(i["description"]) in user for i in others)
    assert "Example 1" not in user and "Worked examples" not in user
    assert "insufficient_evidence" in user and "vague" in user          # vagueness must not trigger retrieval
    assert not re.search(r"\$[a-z_]+", user)
    request = transport.calls[1]
    assert (request["temperature"], request["seed"], request["max_tokens"]) == (0.0, 0, 2048)
    # special labels get their definition from the taxonomy file too
    assert critic.label_definition("none", ctx.taxonomy).startswith("- none: ")
    with pytest.raises(KeyError):
        critic.label_definition("NotALabel", ctx.taxonomy)


def test_critic_sees_all_accumulated_chunks_in_later_rounds(ctx):
    rec, err, trace, transport = run(ctx, [reply("none")], [INSUFFICIENT_1, verdict(True)])
    second_critic = transport.calls[3]["messages"][1]["content"]
    assert transport.kinds == ["diagnosis", "critic", "diagnosis", "critic"]
    assert re.findall(r"^\[((?:rec|ana|ia)\.[^\]]+)\]", second_critic, re.MULTILINE) \
        == trace["rounds"][1]["chunk_ids_shown"]
    assert "whether a base case of two elements" not in second_critic      # no memory of its earlier verdict
    assert trace["stop_reason"] == "sufficient" and trace["n_refinements"] == 1


def test_parse_verdict():
    v = critic.parse_verdict('{"sufficient": false, "missing": " the  course convention ", "query": "merge sort"}')
    assert (v.sufficient, v.missing, v.query) == (False, "the course convention", "merge sort")
    assert v.to_log() == {"sufficient": False, "missing": "the course convention", "query": "merge sort"}
    assert critic.parse_verdict('```json\n{"sufficient": true}\n```').sufficient is True
    lenient = critic.parse_verdict('{"sufficient": "False", "missing": "m", "query": "q"}')
    assert lenient.sufficient is False and lenient.warnings
    kept = critic.parse_verdict('{"sufficient": true, "missing": "nothing", "query": ""}')
    assert kept.sufficient is True and kept.missing == "nothing"
    for bad, match in [('{"sufficient": false, "missing": "m", "query": ""}', "query must be a non-empty"),
                       ('{"sufficient": false, "missing": "", "query": "q"}', "missing must be a non-empty"),
                       ('{"sufficient": 1, "missing": "", "query": ""}', "true or false"),
                       ('{"missing": "", "query": ""}', "true or false"),
                       ('{"sufficient": false, "missing": ["a"], "query": "q"}', "must be a string"),
                       ("no json here", "JSON"), ("", "empty")]:
        with pytest.raises(S.SchemaError, match=match):
            critic.parse_verdict(bad)


# -- scripts/run_condition.py ----------------------------------------------------------

def load_run_condition():
    return load_script("run_condition")


def test_parse_cond_accepts_integers_and_4b():
    rc = load_run_condition()
    assert [rc.parse_cond(c) for c in ("0", "1", "2", "3", "4", "4b", " 4B ")] == [0, 1, 2, 3, 4, "4b", "4b"]
    assert rc.CONDITIONS[4] == "critic_loop" and rc.CONDITIONS["4b"] == "self_consistency"
    import argparse
    for bad in ("5", "4c", "b", "-1", ""):
        with pytest.raises(argparse.ArgumentTypeError):
            rc.parse_cond(bad)


@pytest.mark.parametrize("cond", [0, 1, 2, 3])
def test_conditions_0_to_3_still_run_and_report_tokens_and_calls_per_row(cond, tmp_path, monkeypatch, capsys):
    rc = load_run_condition()
    out = run_script(rc, monkeypatch, capsys, tmp_path, "--cond", str(cond), "--run-id", "run")
    manifest = out["manifest"]
    assert manifest["condition"] == cond and isinstance(manifest["condition"], int)
    assert manifest["condition_name"] == rc.CONDITIONS[cond]
    assert manifest["n_predictions"] == 2 and manifest["n_errors"] == 0
    assert all("trace" not in p for p in out["predictions"])
    if cond == 0:
        assert manifest["model"] == "keyword" and manifest["per_row"] is None
        return
    assert manifest["tokens_per_row"] == {"n_rows": 2, "mean_prompt_tokens": 10.0, "mean_completion_tokens": 5.0,
                                          "mean_total_tokens": 15.0}
    assert manifest["calls_per_row"] == {"n_rows": 2, "mean_calls": 1.0, "min_calls": 1, "max_calls": 1}
    assert manifest["per_row"] == [{"id": i, "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
                                    "calls": 1, "error": False} for i in ("E05.Q04.S1", "E10.Q07.S1")]
    assert manifest["calls"] == {"uncached": 2, "cached": 0}


def test_run_condition_4_writes_traces_and_the_budget_reference(tmp_path, monkeypatch, capsys):
    rc = load_run_condition()
    state = {"critic_calls": 0}

    def content(request):                    # the Critic triggers once per row, then is satisfied
        user = next(m["content"] for m in request["messages"] if m["role"] == "user")
        if "Draft diagnosis" not in user:
            return rc.MOCK_RECORD
        state["critic_calls"] += 1
        return INSUFFICIENT_1 if state["critic_calls"] % 2 == 1 else rc.MOCK_VERDICT

    monkeypatch.setattr(rc, "mock_content", content)
    out = run_script(rc, monkeypatch, capsys, tmp_path, "--cond", "4", "--k", "3", "--run-id", "c4")
    manifest = out["manifest"]
    assert manifest["condition"] == 4 and manifest["condition_name"] == "critic_loop"
    assert manifest["prompt_template"]["name"] == "taxonomy_fewshot_v1"          # condition 3's template
    assert manifest["prompt_template"]["sha256"] == D.load_template("taxonomy_fewshot_v1").sha256
    assert manifest["fewshot"]["name"] == "fewshot_v1" and manifest["retrieval"]["k"] == 3
    assert manifest["temperature"] == 0.0
    critic_block = manifest["critic"]
    assert critic_block["template"]["sha256"] == D.load_template("critic_v1").sha256
    assert (critic_block["max_rounds"], critic_block["requery_k"]) == (2, 3)
    assert critic_block["stop_reasons"] == {"sufficient": 2}
    assert (critic_block["n_rows_critic_called"], critic_block["n_rows_critic_triggered"],
            critic_block["n_rows_refined"]) == (2, 2, 2)
    # per row: diagnosis, Critic, re-diagnosis, Critic = 4 calls of 15 mock tokens each
    assert manifest["per_row"] == [{"id": i, "prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60,
                                    "calls": 4, "error": False} for i in ("E05.Q04.S1", "E10.Q07.S1")]
    assert manifest["calls_per_row"] == {"n_rows": 2, "mean_calls": 4.0, "min_calls": 4, "max_calls": 4}
    assert manifest["tokens_per_row"]["mean_total_tokens"] == 60.0
    assert manifest["tokens"]["total_tokens"] == 120 and manifest["calls"] == {"uncached": 8, "cached": 0}
    assert manifest["budget_reference"]["mean_total_tokens_per_row"] == 60.0
    assert manifest["budget_reference"]["mean_first_call_tokens_per_row"] == 15.0
    for p in out["predictions"]:
        trace = p["trace"]
        assert set(p) >= {"id", "label", "evidence", "confidence", "raw", "citation_valid", "meta", "trace"}
        assert S.Record.from_dict(p).label == "insufficient_evidence"        # still a normal record
        assert trace["stop_reason"] == "sufficient" and trace["n_refinements"] == 1
        assert [len(r["chunk_ids_shown"]) for r in trace["rounds"]] == [3, 6]
        for r in trace["rounds"]:                                  # per round: chunk ids, verdict, query, tokens
            assert {"chunk_ids_shown", "new_chunk_ids", "critic", "query", "tokens", "calls"} <= set(r)
        assert sum(c["total_tokens"] for c in trace["calls"]) == p["meta"]["prompt_tokens"] + p["meta"]["completion_tokens"]

    # --max-rounds 0: one call per row, nothing but condition 3
    out0 = run_script(rc, monkeypatch, capsys, tmp_path, "--cond", "4", "--max-rounds", "0", "--run-id", "c4r0")
    assert out0["manifest"]["calls_per_row"]["max_calls"] == 1
    assert out0["manifest"]["critic"]["stop_reasons"] == {"round_limit": 2}
    assert out0["manifest"]["critic"]["n_rows_critic_called"] == 0


def test_run_condition_rejects_misplaced_options(tmp_path, monkeypatch, capsys):
    rc = load_run_condition()
    for argv in (["--cond", "4b"], ["--cond", "3", "--match-run", "x"], ["--cond", "3", "--max-rounds", "1"],
                 ["--cond", "4", "--max-rounds", "-1"], ["--cond", "5"], ["--cond", "2", "--critic-prompt", "critic_v1"]):
        monkeypatch.setattr("sys.argv", ["run_condition.py", "--mock", *argv])
        with pytest.raises(SystemExit):
            rc.main()
    capsys.readouterr()
