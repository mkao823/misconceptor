"""The Critic's positive control (docs/CRITIC_SPEC.md section 7): the authored control file, its
separation from the eval sheet and from Mohler, the arms, the rates, and the script (mock client)."""

import csv
import json
import re

import pytest
import yaml

from pipeline_helpers import SETTINGS, Scripted, client_for, load_script, reply, verdict
from src import schema as S
from src.baselines import direct as D
from src.baselines import taxonomy_fewshot as TF
from src.config import ANNOTATION_SHEET, REPO_ROOT
from src.pipeline import controls as C
from src.pipeline import loop
from src.retrieval import Retriever, load_corpus

PARQUET = REPO_ROOT / "data" / "raw" / "mohler" / "cleaned-oe-00001.parquet"
CONTROL_FILE = C.CONTROL_DIR / f"{C.DEFAULT_CONTROLS}.yaml"


@pytest.fixture(scope="module")
def ctx():
    taxonomy = S.load_taxonomy()
    return loop.Context(template=D.load_template(loop.DEFAULT_TEMPLATE),
                        critic_template=D.load_template(loop.DEFAULT_CRITIC_TEMPLATE),
                        labels=S.label_set(taxonomy), retriever=Retriever(load_corpus()),
                        taxonomy=taxonomy, fewshot=TF.load_fewshot())


@pytest.fixture(scope="module")
def controls(ctx):
    return C.load_controls(corpus=ctx.retriever.corpus)


# -- the control file ------------------------------------------------------------------

def test_control_file_is_marked_authored_and_covers_every_in_scope_question(controls, ctx):
    raw = yaml.safe_load(CONTROL_FILE.read_text(encoding="utf-8"))
    assert raw["provenance"] == "authored" and all(c["authored"] is True for c in raw["cases"])
    assert "AUTHORED CONTROL MATERIAL" in CONTROL_FILE.read_text(encoding="utf-8")
    assert len(controls.cases) == 16 and len(controls.dependent) == 8 and len(controls.independent) == 8
    assert {c["question_id"] for c in controls.dependent} == set(C.IN_SCOPE_QUESTIONS)
    assert len(C.IN_SCOPE_QUESTIONS) == 7 and set(controls.questions) == set(C.IN_SCOPE_QUESTIONS)
    pairs = {}
    for case in controls.cases:
        pairs.setdefault(case["pair"], []).append(case)
    assert len(pairs) == 8
    for members in pairs.values():                                    # matched: same question, one of each kind
        assert sorted(c["kind"] for c in members) == ["dependent", "independent"]
        assert len({c["question_id"] for c in members}) == 1
    for case in controls.dependent:
        assert case["fact"] and case["fact_ref"].startswith("retrieval_notes.md")
        assert all(chunk in ctx.retriever.corpus for chunk in case["supporting_chunks"])
        assert f"ia.{case['question_id']}" not in case["supporting_chunks"]
    assert {c["independent_kind"] for c in controls.independent} == set(C.INDEPENDENT_KINDS)
    assert len(controls.sha256) == 64


def test_supporting_chunks_are_the_ones_the_retrieval_notes_name(controls):
    """Each dependent case's chunks are named in its question's section of data/corpus/retrieval_notes.md."""
    notes = (REPO_ROOT / "data" / "corpus" / "retrieval_notes.md").read_text(encoding="utf-8")
    sections = dict(re.findall(r"^## (E\d\d\.Q\d\d)\n(.*?)(?=^## )", notes, re.MULTILINE | re.DOTALL))
    for case in controls.dependent:
        section = sections[case["question_id"]]
        assert controls.questions[case["question_id"]]["question"] in section
        for chunk in case["supporting_chunks"]:
            assert f"`{chunk}`" in section, f"{case['id']}: {chunk} is not named for {case['question_id']}"
        fact_no = re.search(r"fact (\d)$", case["fact_ref"]).group(1)
        assert re.search(rf"^\| {fact_no} \|", section, re.MULTILINE), f"{case['id']}: no fact {fact_no}"


def test_control_loader_refuses_unmarked_or_malformed_files(tmp_path, ctx):
    raw = yaml.safe_load(CONTROL_FILE.read_text(encoding="utf-8"))

    def load(mutate):
        data = json.loads(json.dumps(raw, default=str))
        mutate(data)
        (tmp_path / "pc.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return C.load_controls("pc", tmp_path, corpus=ctx.retriever.corpus)

    assert len(load(lambda d: None).cases) == 16
    for mutate, match in [
        (lambda d: d.pop("provenance"), "provenance: authored"),
        (lambda d: d["cases"][0].update(authored=False), "authored: true"),
        (lambda d: d["cases"][0].update(supporting_chunks=["rec.no-such-chunk"]), "unknown chunks"),
        (lambda d: d["cases"][0].update(supporting_chunks=[]), "supporting_chunks"),
        (lambda d: d["cases"][0].update(supporting_chunks=["ia.E03.Q06"]), "own reference answer"),
        (lambda d: d["cases"][1].update(kind="dependent", fact="f", supporting_chunks=["rec.convergence"]), "pair pc01"),
        (lambda d: d["cases"][1].update(independent_kind="other"), "independent_kind"),
        (lambda d: d["cases"][1].update(id="pc01d"), "unique"),
        (lambda d: d["cases"][0].update(question_id="E99.Q99"), "not under 'questions'"),
        (lambda d: d["cases"].__delitem__(slice(0, 2)), "no dependent case for"),
    ]:
        with pytest.raises(S.SchemaError, match=match):
            load(mutate)


# -- separation from the eval sheet and from Mohler --------------------------------------

def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _shingles(text: str, n: int = 6) -> set[str]:
    toks = _norm(text).split()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _assert_no_overlap(controls, answers: list[str], where: str) -> None:
    answers_n = [_norm(a) for a in answers]
    answer_shingles = set().union(*(_shingles(a) for a in answers)) if answers else set()
    for case in controls.cases:
        mine = _norm(case["student_answer"])
        assert len(mine.split()) >= 8, f"{case['id']}: too short to tell apart from a real answer"
        assert not any(mine in a for a in answers_n), f"{case['id']}: student answer appears in {where}"
        assert not any(len(a.split()) >= 5 and a in mine for a in answers_n), f"{case['id']}: contains a {where} answer"
        shared = _shingles(case["student_answer"]) & answer_shingles
        assert not shared, f"{case['id']}: shares the word sequence {sorted(shared)[:2]} with {where}"


def test_control_cases_do_not_appear_in_the_pilot_sheet(controls):
    # Only the question_id, question, instructor_answer and student_answer columns are read; the
    # label columns are never touched.
    with open(ANNOTATION_SHEET, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = [header.index(c) for c in ("id", "question_id", "question", "instructor_answer", "student_answer")]
        cells = [[row[i] for i in cols] for row in reader]
    assert len(cells) == 63
    _assert_no_overlap(controls, [c[4] for c in cells], "the pilot sheet")
    assert not {c["id"] for c in controls.cases} & {c[0] for c in cells}
    # the questions and reference answers ARE the sheet's, so the first pass matches condition 3's prompts
    sheet_questions = {c[1]: (c[2], c[3]) for c in cells}
    assert set(sheet_questions) == set(controls.questions)
    for qid, q in controls.questions.items():
        assert (q["question"], q["instructor_answer"]) == sheet_questions[qid], qid


def test_control_cases_do_not_appear_in_any_mohler_answer(controls):
    if not PARQUET.exists():
        pytest.skip("raw Mohler parquet is not on disk (data/raw/ is gitignored)")
    import pandas as pd

    from scripts.build_corpus import detokenize
    df = pd.read_parquet(PARQUET, columns=["student_answer"])
    assert len(df) == 2273
    _assert_no_overlap(controls, [detokenize(a) for a in df["student_answer"]], "Mohler")


# -- arms ------------------------------------------------------------------------------

def test_arms_withhold_or_force_the_supporting_chunks_in_the_first_pass_only(controls, ctx):
    for case in controls.dependent:
        row = C.case_row(case, controls)
        own = f"ia.{case['question_id']}"
        withheld_hits, always, first_only = loop.first_pass_retrieval(
            row, ctx.retriever, k=4, **C.arm_retrieval_args(case, "withheld"))
        ids = [h.chunk.id for h in withheld_hits]
        assert not set(ids) & set(case["supporting_chunks"]) and own not in ids and len(ids) == 4
        assert first_only == case["supporting_chunks"] and always == [own]      # not withheld from the re-query
        present_hits, _, _ = loop.first_pass_retrieval(row, ctx.retriever, k=4, **C.arm_retrieval_args(case, "present"))
        ids = [h.chunk.id for h in present_hits]
        assert set(case["supporting_chunks"]) <= set(ids) and own not in ids and len(ids) == 4
    for case in controls.independent:
        row = C.case_row(case, controls)
        hits, _, first_only = loop.first_pass_retrieval(row, ctx.retriever, k=4, **C.arm_retrieval_args(case, "natural"))
        cond3 = TF.prepare_row(row, ctx.template, ctx.retriever, ctx.taxonomy, ctx.fewshot, k=4)
        assert [h.chunk.id for h in hits] == [h["id"] for h in cond3["extra_meta"]["retrieved"]] and first_only == []
        with pytest.raises(ValueError):
            C.arm_retrieval_args(case, "withheld")


def critic_needing(chunk_id: str, query: str):
    """A scripted Critic that is satisfied only when ``chunk_id`` is among the excerpts shown."""
    def answer(request):
        user = request["messages"][1]["content"]
        return verdict(True) if f"[{chunk_id}]" in user else verdict(False, f"what {chunk_id} says", query)
    return answer


def test_run_arm_logs_trigger_and_recovery_and_agrees_with_the_loop(controls, ctx):
    case = next(c for c in controls.cases if c["id"] == "pc04d")           # merge sort, two elements
    partner = next(c for c in controls.cases if c["id"] == "pc04i")
    chunk = "rec.merge-sort-base-case"
    assert case["supporting_chunks"] == [chunk]
    critic_script = critic_needing(chunk, "merge sort base case size 2 acceptable")

    def arm(which_case, name):
        transport = Scripted([reply("none")], [critic_script])
        return C.run_arm(which_case, name, controls, client_for(transport), ctx, k=4, **SETTINGS), transport

    withheld, transport = arm(case, "withheld")
    assert transport.kinds == ["diagnosis", "critic"]                     # first pass and one Critic call, no more
    assert withheld["triggered"] is True and chunk not in withheld["chunk_ids_shown"]
    assert withheld["supporting_in_natural_top_k"] == [chunk]
    assert chunk in withheld["requery"]["new_chunk_ids"] and len(withheld["requery"]["new_chunk_ids"]) == 4
    assert not set(withheld["requery"]["new_chunk_ids"]) & set(withheld["chunk_ids_shown"])
    assert withheld["recovered"] == {"chunk_ids": [chunk], "any": True, "all": True}
    assert withheld["n_calls"] == 2 and withheld["tokens"]["total_tokens"] == sum(c["total_tokens"] for c in withheld["calls"])
    # the request is condition 3's prompt for this invented answer, with the chunk gone
    user = transport.calls[0]["messages"][1]["content"]
    assert "Student's answer:\n" + C.case_row(case, controls)["student_answer"] in user and f"[{chunk}]" not in user

    present, _ = arm(case, "present")
    assert present["triggered"] is False and chunk in present["chunk_ids_shown"]
    assert present["requery"] is None and present["recovered"] is None
    natural, _ = arm(partner, "natural")
    assert natural["arm"] == "natural" and natural["triggered"] is False and natural["independent_kind"] == "matches_reference"

    # the arm is the loop's own first round: same chunks, same verdict, same re-query
    transport = Scripted([reply("none")], [critic_script])
    _, _, trace = loop.run_row(C.case_row(case, controls), client_for(transport), ctx, k=4, max_rounds=1,
                               first_pass_exclude=case["supporting_chunks"], **SETTINGS)
    assert trace["rounds"][0]["chunk_ids_shown"] == withheld["chunk_ids_shown"]
    assert {k: trace["rounds"][0]["critic"][k] for k in ("sufficient", "missing", "query")} == withheld["critic"]
    assert trace["rounds"][1]["new_chunk_ids"] == withheld["requery"]["new_chunk_ids"]

    # a re-query that misses the withheld chunk is reported as not recovered
    transport = Scripted([reply("none")], [verdict(False, "something else", "insertion sort best case sorted array")])
    missed = C.run_arm(case, "withheld", controls, client_for(transport), ctx, k=4, **SETTINGS)
    assert missed["triggered"] is True and missed["recovered"] == {"chunk_ids": [], "any": False, "all": False}
    # errors are logged, not counted as a verdict
    failed = C.run_arm(case, "withheld", controls, client_for(Scripted(["junk"], [verdict(True)])), ctx, k=4, **SETTINGS)
    assert failed["error"]["where"] == "first_pass" and failed["triggered"] is None and failed["n_calls"] == 2
    broken = C.run_arm(case, "withheld", controls, client_for(Scripted([reply("none")], ["junk"])), ctx, k=4, **SETTINGS)
    assert broken["error"]["where"] == "critic" and broken["triggered"] is None and broken["n_calls"] == 3


def fake_arm(case, arm, triggered, recovered=None, kind=None):
    return {"case": case, "pair": case[:4], "question_id": "E05.Q04", "arm": arm, "triggered": triggered,
            "kind": "independent" if arm == "natural" else "dependent", "independent_kind": kind,
            "recovered": recovered, "error": None if triggered is not None else {"where": "critic"},
            "n_calls": 2, "tokens": {"total_tokens": 100}}


def test_summarize_reports_each_rate_with_its_counts():
    yes = {"chunk_ids": ["x"], "any": True, "all": True}
    no = {"chunk_ids": [], "any": False, "all": False}
    arms = [fake_arm("pc01d", "withheld", True, yes), fake_arm("pc01d", "present", False),
            fake_arm("pc02d", "withheld", True, no), fake_arm("pc02d", "present", True),
            fake_arm("pc03d", "withheld", False), fake_arm("pc03d", "present", False),
            fake_arm("pc04d", "withheld", None), fake_arm("pc04d", "present", False),       # Critic failed
            fake_arm("pc01i", "natural", False, kind="matches_reference"),
            fake_arm("pc02i", "natural", True, kind="vague"),
            fake_arm("pc03i", "natural", False, kind="vague")]
    s = C.summarize(arms)
    assert s["arms"]["withheld"] == {"n": 4, "n_judged": 3, "n_errors": 1, "n_triggered": 2, "trigger_rate": 0.6667}
    assert s["arms"]["present"] == {"n": 4, "n_judged": 4, "n_errors": 0, "n_triggered": 1, "trigger_rate": 0.25}
    assert s["arms"]["natural"] == {"n": 3, "n_judged": 3, "n_errors": 0, "n_triggered": 1, "trigger_rate": 0.3333}
    assert s["natural_by_kind"] == {"matches_reference": {"n_judged": 1, "n_triggered": 0},
                                    "vague": {"n_judged": 2, "n_triggered": 1}}
    assert s["recovery"] == {"n_withheld_triggered": 2, "n_recovered_any": 1, "n_recovered_all": 1,
                             "rate_any_given_triggered": 0.5, "rate_any_over_withheld_judged": 0.3333}
    assert s["paired"] == {"n_cases_both_arms_judged": 3, "n_withheld_only": 1, "n_both": 1, "n_neither": 1,
                           "n_present_only": 0}
    assert s["cost"] == {"n_arms": 11, "n_calls": 22, "total_tokens": 1100, "mean_tokens_per_arm": 100.0,
                         "mean_calls_per_arm": 2.0}
    empty = C.summarize([])
    assert empty["arms"]["withheld"]["trigger_rate"] is None and empty["recovery"]["rate_any_given_triggered"] is None


# -- the script ------------------------------------------------------------------------

def test_run_positive_control_script_writes_manifest_arms_and_summary(tmp_path, monkeypatch, capsys):
    module = load_script("run_positive_control")

    def content(request):          # insufficient exactly when E05.Q04 is judged without its base-case chunk
        user = next(m["content"] for m in request["messages"] if m["role"] == "user")
        if "Draft diagnosis" not in user:
            return reply("none")
        if "base case for a recursive implementation of merge sort" in user and "[rec.merge-sort-base-case]" not in user:
            return verdict(False, "the course's merge sort base case", "merge sort base case size 2 acceptable")
        return verdict(True)

    monkeypatch.setattr(module, "mock_content", content)
    monkeypatch.setattr("sys.argv", ["run_positive_control.py", "--mock", "--no-cache", "--out-root", str(tmp_path),
                                     "--run-id", "pc"])
    module.main()
    printed = capsys.readouterr().out
    assert "triggered, withheld: 1/8" in printed and "triggered, present: 0/8" in printed
    manifest = json.loads((tmp_path / "pc" / "manifest.json").read_text())
    arms = [json.loads(line) for line in (tmp_path / "pc" / "arms.jsonl").read_text().splitlines()]
    summary_md = (tmp_path / "pc" / "summary.md").read_text()
    assert manifest["kind"] == "critic_positive_control" and manifest["transport"] == "mock"
    assert manifest["controls"]["sha256"] == C.load_controls().sha256 and manifest["controls"]["n_cases"] == 16
    assert manifest["critic_template"]["sha256"] == D.load_template("critic_v1").sha256
    assert manifest["prompt_template"]["name"] == "taxonomy_fewshot_v1" and manifest["retrieval"]["k"] == 4
    assert len(arms) == 24                                           # 8 dependent x 2 arms + 8 non-dependent x 1
    assert sorted(a["arm"] for a in arms).count("withheld") == 8 and sum(a["arm"] == "natural" for a in arms) == 8
    assert manifest["calls"] == {"uncached": 48, "cached": 0}        # one diagnosis and one Critic call per arm
    s = manifest["summary"]
    assert (s["arms"]["withheld"]["n_triggered"], s["arms"]["present"]["n_triggered"],
            s["arms"]["natural"]["n_triggered"]) == (1, 0, 0)
    assert s["recovery"]["n_recovered_any"] == 1 and s["paired"]["n_withheld_only"] == 1
    assert s["cost"]["n_calls"] == 48 and s["cost"]["total_tokens"] == manifest["tokens"]["total_tokens"]
    triggered = [a for a in arms if a["triggered"]]
    assert [(a["case"], a["arm"]) for a in triggered] == [("pc04d", "withheld")]
    assert "| pc04d | E05.Q04 | withheld | none | yes |" in summary_md and "1/8 (12%)" in summary_md
    assert "not evidence for or against" in summary_md and "authored control material" in summary_md
