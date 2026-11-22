"""Conditions 2 (RAG) and 3 (taxonomy + few-shot): prompts, retrieved-span validation,
few-shot provenance, and the run script, all with a mock client (no network)."""

import csv
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from src import schema as S
from src.baselines import direct as D
from src.baselines import rag
from src.baselines import taxonomy_fewshot as TF
from src.config import ANNOTATION_SHEET, PROMPT_DIR, REPO_ROOT
from src.eval import metrics as M
from src.llm import LLMClient, MockTransport
from src.retrieval import CORPUS_DIR, Retriever, instructor_answer_chunk_id, load_corpus

CFG = {"default_model": "fake-model", "default_provider": "fake",
       "providers": {"fake": {"base_url": None, "api_key_env": "X", "api_key_required": False, "models": []}}}
# A synthetic row (not from the sheet) on an in-scope question id.
ROW = {"id": "E05.Q04.SYN", "question_id": "E05.Q04",
       "question": "What is the base case for a recursive implementation of merge sort?",
       "instructor_answer": "When the size of the array to be sorted is 1 (or 2)",
       "student_answer": "it stops when the piece has two   elements left"}
IN_SCOPE = ["E03.Q06", "E05.Q04", "E05.Q03", "E10.Q07", "E12.Q10", "E03.Q07", "E11.Q09"]
PARQUET = REPO_ROOT / "data" / "raw" / "mohler" / "cleaned-oe-00001.parquet"


@pytest.fixture(scope="module")
def retriever():
    return Retriever(load_corpus())


@pytest.fixture(scope="module")
def taxonomy():
    return S.load_taxonomy()


@pytest.fixture(scope="module")
def fewshot():
    return TF.load_fewshot()


def client_for(reply, tmp_path):
    transport = MockTransport(reply, prompt_tokens=1800, completion_tokens=300)
    return LLMClient("fake-model", transport=transport, cache_dir=tmp_path, models_cfg=CFG), transport


def reply(label="none", evidence=(), confidence=0.9) -> str:
    return json.dumps({"label": label, "evidence": list(evidence), "confidence": confidence})


# -- retrieved-span validation ---------------------------------------------------

CHUNKS = ["The base case is reached when the size of the array\nto be sorted is 1 (or 2).",
          "Merge sort splits the array into two halves."]
LABELS = ["BCwrite", "none", "other_error", "insufficient_evidence"]


def validate(evidence, **kwargs):
    return S.validate_record({"label": "none", "confidence": 0.5, "evidence": evidence}, row_id="r",
                             student_answer="two elements left", labels=LABELS, **kwargs)


def test_verbatim_retrieved_span_is_valid_after_whitespace_normalization():
    rec = validate([{"source": "retrieved", "span": "size of the array to be   sorted is 1 (or 2)"},
                    {"source": "student_answer", "span": "two elements"}], retrieved_chunks=CHUNKS)
    assert rec.citation_valid and rec.invalid_spans == [] and rec.invalid_by_source == {}
    assert rec.sources_checked == ["student_answer", "retrieved"]
    assert rec.retrieved_spans == ["size of the array to be   sorted is 1 (or 2)"]


def test_fabricated_retrieved_span_is_rejected():
    fabricated = "the base case is an empty array"
    rec = validate([{"source": "retrieved", "span": fabricated},
                    {"source": "retrieved", "span": "Merge sort splits the array"},
                    {"source": "student_answer", "span": "two elements"}], retrieved_chunks=CHUNKS)
    assert rec.citation_valid is False
    assert rec.invalid_spans == [fabricated] and rec.invalid_by_source == {"retrieved": [fabricated]}
    evidence = [S.Evidence("retrieved", fabricated)]
    assert S.check_citations(evidence, "two elements left", CHUNKS) == (False, [fabricated])
    assert S.invalid_evidence(evidence, "two elements left", CHUNKS) == {"retrieved": [fabricated]}


@pytest.mark.parametrize("span", [
    "sorted is 1 (or 2). Merge sort splits",      # stitched across two chunks: must lie inside ONE chunk
    "size of the array ... is 1 (or 2)",          # ellipsis
    "The Base Case is reached",                   # case changed
    "two elements left",                          # the student's words are not retrieved material
])
def test_near_miss_retrieved_spans_are_rejected(span):
    rec = validate([{"source": "retrieved", "span": span}], retrieved_chunks=CHUNKS)
    assert rec.citation_valid is False and rec.invalid_by_source == {"retrieved": [span]}


def test_retrieved_span_with_nothing_shown_is_rejected_and_unchecked_sources_are_ignored():
    span = {"source": "retrieved", "span": "Merge sort splits the array"}
    assert validate([span], retrieved_chunks=[]).citation_valid is False       # nothing was shown
    rec = validate([span])                                                     # conditions 0 and 1: not checked
    assert rec.citation_valid is True and rec.sources_checked == ["student_answer"]


def test_taxonomy_spans_are_checked_against_the_taxonomy_text_shown():
    text = "- BCwrite (recursion): the student cannot supply a base case."
    ok = validate([{"source": "taxonomy", "span": "cannot supply a base case"}], taxonomy_text=text)
    bad = validate([{"source": "taxonomy", "span": "always forgets the base case"}], taxonomy_text=text)
    assert ok.citation_valid and ok.sources_checked == ["student_answer", "taxonomy"]
    assert bad.citation_valid is False and bad.invalid_by_source == {"taxonomy": ["always forgets the base case"]}


def test_citation_validity_metric_is_reported_per_source():
    good = validate([{"source": "student_answer", "span": "two elements"},
                     {"source": "retrieved", "span": "Merge sort splits"}], retrieved_chunks=CHUNKS).to_dict()
    bad_retrieved = validate([{"source": "student_answer", "span": "two elements"},
                              {"source": "retrieved", "span": "made up"}], retrieved_chunks=CHUNKS).to_dict()
    bad_student = validate([{"source": "student_answer", "span": "three elements"}], retrieved_chunks=CHUNKS).to_dict()
    unchecked = validate([{"source": "retrieved", "span": "made up"}]).to_dict()          # condition 1 style
    cv = M.citation_validity([good, bad_retrieved, bad_student, unchecked])
    assert (cv["n_with_student_spans"], cv["n_valid"]) == (3, 2)        # student validity ignores the retrieved span
    assert cv["retrieved"] == {"n_with_spans": 2, "n_valid": 1, "rate": 0.5}
    assert cv["taxonomy"] == {"n_with_spans": 0, "n_valid": 0, "rate": None}
    assert cv["rate_all"] == pytest.approx(2 / 4)
    assert S.Record.from_dict(bad_retrieved).invalid_by_source == {"retrieved": ["made up"]}


# -- condition 2 -------------------------------------------------------------------

def test_condition_2_prompt_sections(retriever, taxonomy):
    labels = S.label_set(taxonomy)
    prepared = rag.prepare_row(ROW, D.load_template("rag_v1"), labels, retriever, k=4)
    system, user = prepared["messages"][0], prepared["messages"][1]["content"]
    assert system["role"] == "system" and "JSON" in system["content"]
    hits = prepared["extra_meta"]["retrieved"]
    assert len(hits) == 4 and hits[0]["id"] == "rec.merge-sort-base-case" and [h["rank"] for h in hits] == [1, 2, 3, 4]
    # the sections, in order
    order = ["Exam question:", ROW["question"], "Instructor's reference answer:", ROW["instructor_answer"],
             "Course material retrieved", f"[{hits[0]['id']}]", f"[{hits[3]['id']}]", "Student's answer:",
             ROW["student_answer"], "- BFneverExecute", "- none:", '"source": "retrieved"']
    positions = [user.index(s) for s in order]
    assert positions == sorted(positions)
    for h, text in zip(hits, prepared["retrieved_chunks"]):
        assert f"[{h['id']}]" in user and text in user and text == retriever.corpus.get(h["id"]).text
    # the reference answer is already in the prompt, so its own chunk is withheld from retrieval
    assert prepared["extra_meta"]["withheld_chunk_ids"] == ["ia.E05.Q04"]
    assert "[ia.E05.Q04]" not in user
    # still no taxonomy descriptions and no examples
    for item in taxonomy["items"]:
        assert f"- {item['id']}\n" in user
        assert item["description"].split(".")[0] not in user
    assert "Example 1" not in user and not re.search(r"\$[a-z_]+", user)
    assert prepared["taxonomy_text"] is None


def test_condition_2_retrieval_options(retriever):
    own = instructor_answer_chunk_id("E05.Q04")
    default, withheld = rag.retrieve_for_row(ROW, retriever, k=3)
    assert withheld == [own] and own not in [h.chunk.id for h in default]
    kept, withheld = rag.retrieve_for_row(ROW, retriever, k=3, keep_own_reference=True)
    assert withheld == [] and own in [h.chunk.id for h in kept]
    hits, withheld = rag.retrieve_for_row(ROW, retriever, k=3, exclude=["rec.merge-sort-base-case"])
    assert withheld == ["rec.merge-sort-base-case", "ia.E05.Q04"]
    assert not {"rec.merge-sort-base-case", "ia.E05.Q04"} & {h.chunk.id for h in hits}
    assert rag.format_chunks([]) == rag.NO_CHUNKS


def test_condition_2_predict_row_logs_chunks_and_checks_retrieved_spans(retriever, tmp_path):
    labels = S.label_set()
    template = D.load_template("rag_v1")
    quote = "a base case of size 2 is equally acceptable"
    client, transport = client_for(reply("none", [{"source": "retrieved", "span": quote}]), tmp_path)
    rec, err = rag.predict_row(ROW, client, template, labels, retriever, k=4, max_repairs=0)
    assert err is None and rec.label == "none" and rec.citation_valid
    assert rec.sources_checked == ["student_answer", "retrieved"]
    assert [h["id"] for h in rec.meta["retrieved"]][0] == "rec.merge-sort-base-case"
    assert all(set(h) == {"id", "score", "rank"} and h["score"] > 0 for h in rec.meta["retrieved"])
    assert rec.meta["prompt_tokens"] == 1800 and rec.meta["completion_tokens"] == 300
    assert rec.meta["prompt_chars"] == D.prompt_chars(transport.calls[0]["messages"])
    assert len(transport.calls) == 1                                    # one model call

    fabricated = "merge sort stops when the array is empty"
    client, _ = client_for(reply("BCwrite", [{"source": "student_answer", "span": "two elements left"},
                                              {"source": "retrieved", "span": fabricated}]), tmp_path / "b")
    rec, err = rag.predict_row(ROW, client, template, labels, retriever, k=4, max_repairs=0)
    assert err is None and rec.citation_valid is False and rec.invalid_by_source == {"retrieved": [fabricated]}

    # a chunk that was withheld was not shown, so quoting it is a fabricated citation
    client, _ = client_for(reply("none", [{"source": "retrieved", "span": quote}]), tmp_path / "c")
    rec, _ = rag.predict_row(ROW, client, template, labels, retriever, k=4, max_repairs=0,
                             exclude=["rec.merge-sort-base-case"])
    assert rec.citation_valid is False and "rec.merge-sort-base-case" in rec.meta["withheld_chunk_ids"]

    client, _ = client_for("not json", tmp_path / "d")
    rec, err = rag.predict_row(ROW, client, template, labels, retriever, k=2, max_repairs=0)
    assert rec is None and err["stage"] == "parse" and len(err["retrieved"]) == 2 and err["usage"]["prompt_tokens"] == 1800


# -- condition 3 -------------------------------------------------------------------

def test_condition_3_prompt_sections(retriever, taxonomy, fewshot):
    prepared = TF.prepare_row(ROW, D.load_template("taxonomy_fewshot_v1"), retriever, taxonomy, fewshot, k=4)
    user = prepared["messages"][1]["content"]
    hits = prepared["extra_meta"]["retrieved"]
    order = ["Misconception catalogue", "- BFneverExecute (recursion):", "- BObestWorstSwapped (big_o):",
             "Special labels", "- none:", "- insufficient_evidence:", "Worked examples", "Example 1",
             f"Example {len(fewshot.examples)}", "Exam question:\n" + ROW["question"],
             "Instructor's reference answer:\n" + ROW["instructor_answer"], "Course material retrieved",
             f"[{hits[0]['id']}]", "Student's answer:\n" + ROW["student_answer"], '"source": "taxonomy"']
    positions = [user.index(s) for s in order]
    assert positions == sorted(positions)
    # full taxonomy text: id, description and notes of every item; the three special-label definitions
    for item in taxonomy["items"]:
        assert f"- {item['id']} ({item['concept']}): {S.normalize_ws(item['description'])}" in user
        if item.get("notes"):
            assert f"Notes: {S.normalize_ws(item['notes'])}" in user
        for phrase in item.get("trigger_phrases") or []:
            assert f'"{phrase}"' not in user                     # keyword-baseline material stays out
    assert len(taxonomy["special_labels"]) == 3
    for sp in taxonomy["special_labels"]:
        assert f"- {sp['id']}: {S.normalize_ws(sp['definition'])}" in user
    # every few-shot example with its expected output; maintainers' rationales are not shown
    for ex in fewshot.examples:
        assert S.normalize_ws(ex["student_answer"]) in user and f'"label": "{ex["output"]["label"]}"' in user
        assert S.normalize_ws(ex["rationale"]) not in user
    # condition 2's retrieved chunks are still there
    for text in prepared["retrieved_chunks"]:
        assert text in user
    assert len(hits) == 4 and not re.search(r"\$[a-z_]+", user)
    assert prepared["taxonomy_text"] == TF.taxonomy_text(taxonomy)
    lines = prepared["taxonomy_text"].splitlines()
    assert len(lines) == len(taxonomy["items"]) + 3 and all(line in user for line in lines)


def test_condition_3_predict_row_is_single_pass_and_checks_all_sources(retriever, taxonomy, fewshot, tmp_path):
    labels = S.label_set(taxonomy)
    template = D.load_template("taxonomy_fewshot_v1")
    item = next(i for i in taxonomy["items"] if i["id"] == "BCwrite")
    tax_quote = S.normalize_ws(item["description"])[:60]
    evidence = [{"source": "student_answer", "span": "two elements left"},
                {"source": "retrieved", "span": "a base case of size 2 is equally acceptable"},
                {"source": "taxonomy", "span": tax_quote}]
    client, transport = client_for(reply("BCwrite", evidence), tmp_path)
    rec, err = TF.predict_row(ROW, client, template, labels, retriever, taxonomy, fewshot, k=4, max_repairs=0)
    assert err is None and rec.label == "BCwrite" and rec.citation_valid
    assert rec.sources_checked == ["student_answer", "retrieved", "taxonomy"]
    assert len(transport.calls) == 1 and len(rec.meta["retrieved"]) == 4

    evidence[2] = {"source": "taxonomy", "span": "students always get merge sort wrong"}
    client, _ = client_for(reply("BCwrite", evidence), tmp_path / "b")
    rec, _ = TF.predict_row(ROW, client, template, labels, retriever, taxonomy, fewshot, k=4, max_repairs=0)
    assert rec.citation_valid is False and list(rec.invalid_by_source) == ["taxonomy"]


# -- few-shot examples ---------------------------------------------------------------

def test_fewshot_file_is_marked_authored_and_covers_the_required_labels(fewshot, taxonomy):
    raw = yaml.safe_load((PROMPT_DIR / "fewshot_v1.yaml").read_text(encoding="utf-8"))
    assert raw["provenance"] == "authored" and all(ex["authored"] is True for ex in raw["examples"])
    labels = fewshot.labels
    assert {"none", "other_error", "insufficient_evidence"} <= set(labels)
    concept = {item["id"]: item["concept"] for item in taxonomy["items"]}
    tax_labels = [l for l in labels if l in concept]
    assert 4 <= len(set(tax_labels)) <= 5 and len(tax_labels) == len(set(tax_labels))
    assert sum(1 for l in set(tax_labels) if concept[l] == "big_o") >= 2
    for ex in fewshot.examples:
        out = ex["output"]
        spans = [e["span"] for e in out["evidence"]]
        assert all(e["source"] == "student_answer" for e in out["evidence"])
        assert all(S.normalize_ws(s) in S.normalize_ws(ex["student_answer"]) for s in spans)
        assert bool(spans) == (out["label"] not in ("none", "insufficient_evidence"))
    assert len(fewshot.sha256) == 64


def test_fewshot_loader_refuses_unmarked_or_invalid_files(tmp_path):
    raw = yaml.safe_load((PROMPT_DIR / "fewshot_v1.yaml").read_text(encoding="utf-8"))

    def write(mutate) -> None:
        data = json.loads(json.dumps(raw, default=str))
        mutate(data)
        (tmp_path / "fs.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    write(lambda d: None)
    assert len(TF.load_fewshot("fs", tmp_path).examples) == len(raw["examples"])
    write(lambda d: d.pop("provenance"))
    with pytest.raises(S.SchemaError, match="provenance: authored"):
        TF.load_fewshot("fs", tmp_path)
    write(lambda d: d["examples"][0].update(authored=False))
    with pytest.raises(S.SchemaError, match="authored: true"):
        TF.load_fewshot("fs", tmp_path)
    write(lambda d: d["examples"][0]["output"].update(label="NotALabel"))
    with pytest.raises(S.SchemaError, match="label set"):
        TF.load_fewshot("fs", tmp_path)
    write(lambda d: d["examples"][0]["output"]["evidence"][0].update(span="words the student never wrote"))
    with pytest.raises(S.SchemaError, match="not clean"):
        TF.load_fewshot("fs", tmp_path)


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _shingles(text: str, n: int = 6) -> set[str]:
    toks = _norm(text).split()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _assert_no_overlap(fewshot, answers: list[str], questions: list[str], where: str) -> None:
    answers_n = [_norm(a) for a in answers]
    answer_shingles = set().union(*(_shingles(a) for a in answers)) if answers else set()
    questions_n = {_norm(q) for q in questions}
    for ex in fewshot.examples:
        mine = _norm(ex["student_answer"])
        assert _norm(ex["question"]) not in questions_n, f"{ex['id']}: question is a {where} question"
        assert not any(mine in a for a in answers_n), f"{ex['id']}: student answer appears in {where}"
        assert not any(len(a.split()) >= 5 and a in mine for a in answers_n), f"{ex['id']}: contains a {where} answer"
        shared = _shingles(ex["student_answer"]) & answer_shingles
        assert not shared, f"{ex['id']}: shares the word sequence {sorted(shared)[:2]} with {where}"


def test_fewshot_examples_do_not_appear_in_the_pilot_sheet(fewshot):
    # Only the question and student_answer columns are read; the label columns are never touched.
    with open(ANNOTATION_SHEET, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        q_col, a_col = header.index("question"), header.index("student_answer")
        cells = [(row[q_col], row[a_col]) for row in reader]
    assert len(cells) == 63
    _assert_no_overlap(fewshot, [a for _, a in cells], sorted({q for q, _ in cells}), "the pilot sheet")


def test_fewshot_examples_do_not_appear_in_any_mohler_answer(fewshot):
    if not PARQUET.exists():
        pytest.skip("raw Mohler parquet is not on disk (data/raw/ is gitignored)")
    import pandas as pd

    from scripts.build_corpus import detokenize
    df = pd.read_parquet(PARQUET, columns=["question", "student_answer"])
    assert len(df) == 2273
    _assert_no_overlap(fewshot, [detokenize(a) for a in df["student_answer"]],
                       sorted({detokenize(q) for q in df["question"]}), "Mohler")


# -- corpus documentation ----------------------------------------------------------

def test_retrieval_notes_cover_the_in_scope_questions_and_name_real_chunks():
    text = (CORPUS_DIR / "retrieval_notes.md").read_text(encoding="utf-8")
    corpus = load_corpus()
    for qid in IN_SCOPE:
        assert re.search(rf"^## {re.escape(qid)}\b", text, re.MULTILINE), f"no section for {qid}"
    cited = set(re.findall(r"`((?:rec|ana|ia)\.[A-Za-z0-9.-]+)`", text))
    assert cited and all(c in corpus for c in cited), sorted(c for c in cited if c not in corpus)
    for doc in ("README.md", "retrieval_notes.md"):                 # documentation is never indexed
        assert not any(c.path == doc for c in corpus.chunks)


# -- scripts/run_condition.py with the mock client -----------------------------------

def load_run_condition():
    spec = importlib.util.spec_from_file_location("run_condition", REPO_ROOT / "scripts" / "run_condition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_sheet(path: Path) -> Path:
    rows = [{"id": "E05.Q04.S1", "question_id": "E05.Q04", "question": ROW["question"],
             "instructor_answer": ROW["instructor_answer"], "student_answer": "two elements", "score_avg": "5.0"},
            {"id": "E10.Q07.S1", "question_id": "E10.Q07",
             "question": "How many comparisons does it take to find an element in a binary search tree?",
             "instructor_answer": "The height of the tree (or log of the number of elements in the tree) .",
             "student_answer": "about half of the nodes", "score_avg": "1.0"}]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("cond", [2, 3])
def test_run_condition_writes_retrieval_details(cond, tmp_path, monkeypatch, capsys):
    rc = load_run_condition()
    sheet = synthetic_sheet(tmp_path / "sheet.csv")
    monkeypatch.setattr("sys.argv", ["run_condition.py", "--cond", str(cond), "--mock", "--no-cache", "--k", "3",
                                     "--sheet", str(sheet), "--out-root", str(tmp_path), "--run-id", "run",
                                     "--exclude-chunk", "ana.bst-search-height"])
    rc.main()
    capsys.readouterr()
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    corpus = load_corpus()
    assert manifest["condition"] == cond and manifest["condition_name"] == rc.CONDITIONS[cond]
    retrieval = manifest["retrieval"]
    assert (retrieval["backend"], retrieval["k"], retrieval["corpus_hash"]) == ("bm25", 3, corpus.hash)
    assert retrieval["excluded_chunk_ids"] == ["ana.bst-search-height"] and retrieval["n_chunks"] == len(corpus)
    template = {2: "rag_v1", 3: "taxonomy_fewshot_v1"}[cond]
    assert manifest["prompt_template"]["name"] == template
    assert manifest["prompt_template"]["sha256"] == D.load_template(template).sha256
    assert manifest["tokens_per_row"] == {"n_rows": 2, "mean_prompt_tokens": 10.0, "mean_completion_tokens": 5.0,
                                          "mean_total_tokens": 15.0}
    if cond == 3:
        assert manifest["fewshot"]["name"] == "fewshot_v1" and manifest["fewshot"]["sha256"] == TF.load_fewshot().sha256
        assert len(manifest["taxonomy"]["rendered_sha256"]) == 64
    else:
        assert manifest["fewshot"] is None
    preds = [json.loads(l) for l in (tmp_path / "run" / "predictions.jsonl").read_text().splitlines()]
    assert [p["id"] for p in preds] == ["E05.Q04.S1", "E10.Q07.S1"] and manifest["n_errors"] == 0
    for p in preds:
        meta = p["meta"]
        assert len(meta["retrieved"]) == 3 and all(h["id"] in corpus for h in meta["retrieved"])
        assert "ana.bst-search-height" in meta["withheld_chunk_ids"]
        assert "ana.bst-search-height" not in [h["id"] for h in meta["retrieved"]]
        assert meta["prompt_tokens"] == 10 and meta["completion_tokens"] == 5
        assert "retrieved" in p["sources_checked"]


def test_run_condition_rejects_unknown_chunk_ids(tmp_path, monkeypatch):
    rc = load_run_condition()
    sheet = synthetic_sheet(tmp_path / "sheet.csv")
    monkeypatch.setattr("sys.argv", ["run_condition.py", "--cond", "2", "--mock", "--no-cache", "--sheet", str(sheet),
                                     "--out-root", str(tmp_path), "--exclude-chunk", "rec.nope"])
    with pytest.raises(SystemExit, match="rec.nope"):
        rc.main()
    assert not any(p.is_dir() for p in tmp_path.iterdir())


class FakeClient:
    provider, model = "ollama", "gpt-oss:20b"

    def __init__(self, context_length, cached=False):
        self.context_length, self.cached, self.lookups = context_length, cached, 0

    def is_cached(self, messages, **kwargs):
        return self.cached

    def loaded_context_length(self):
        self.lookups += 1
        return self.context_length


def test_context_window_check_stops_a_run_that_would_be_truncated():
    rc = load_run_condition()
    settings = {"temperature": 0.0, "seed": 0, "max_tokens": 2048, "json_mode": True, "max_repairs": 1}
    prepared = [{"messages": [{"role": "user", "content": "x" * 21000}]}]     # about condition 3's size
    with pytest.raises(SystemExit, match="OLLAMA_CONTEXT_LENGTH"):
        rc.check_context_window(FakeClient(4096), prepared, settings)
    info = rc.check_context_window(FakeClient(16384), prepared, settings)
    assert info == {"context_length": 16384, "max_prompt_chars": 21000, "estimated_tokens_needed": 7000 + 2048}
    assert rc.check_context_window(FakeClient(None), prepared, settings)["context_length"] is None   # not Ollama
    cached = FakeClient(4096, cached=True)                                    # nothing to send: no lookup
    assert rc.check_context_window(cached, prepared, settings)["context_length"] is None and cached.lookups == 0
    small = [{"messages": [{"role": "user", "content": "x" * 2600}]}]         # condition 1 fits the default window
    assert rc.check_context_window(FakeClient(4096), small, settings)["context_length"] == 4096
