import pytest

from src import schema as S

LABELS = ["BOsearchVsSort", "RCreturnIsRequired", "none", "other_error", "insufficient_evidence"]
ANSWER = "It takes   n log n\ncomparisons to find the node."


def test_valid_record_with_verbatim_span():
    rec = S.validate_record({"label": "BOsearchVsSort", "confidence": 0.8,
                             "evidence": [{"source": "student_answer", "span": "n log n comparisons"}]},
                            row_id="r1", student_answer=ANSWER, labels=LABELS)
    assert rec.label == "BOsearchVsSort" and rec.confidence == 0.8
    assert rec.citation_valid is True and rec.invalid_spans == [] and rec.warnings == []


def test_fabricated_span_is_flagged_not_rejected():
    rec = S.validate_record({"label": "BOsearchVsSort", "confidence": 0.9,
                             "evidence": [{"source": "student_answer", "span": "the tree is balanced"},
                                          {"source": "student_answer", "span": "find the node"}]},
                            row_id="r1", student_answer=ANSWER, labels=LABELS)
    assert rec.citation_valid is False
    assert rec.invalid_spans == ["the tree is balanced"]


def test_whitespace_normalized_match():
    rec = S.validate_record({"label": "none", "confidence": 1,
                             "evidence": [{"source": "student_answer", "span": "n  log n\n comparisons"}]},
                            row_id="r1", student_answer=ANSWER, labels=LABELS)
    assert rec.citation_valid is True


def test_retrieved_and_taxonomy_spans_not_checked_against_answer():
    rec = S.validate_record({"label": "none", "confidence": 0.5,
                             "evidence": [{"source": "retrieved", "span": "anything"},
                                          {"source": "taxonomy", "span": "anything else"}]},
                            row_id="r1", student_answer=ANSWER, labels=LABELS)
    assert rec.citation_valid is True and rec.student_spans == []


def test_no_evidence_is_vacuously_valid():
    rec = S.validate_record({"label": "insufficient_evidence", "confidence": 0.5, "evidence": []},
                            row_id="r1", student_answer=ANSWER, labels=LABELS)
    assert rec.citation_valid is True


@pytest.mark.parametrize("obj,msg", [
    ({"label": "NotALabel", "confidence": 0.5, "evidence": []}, "not in the label set"),
    ({"label": "", "confidence": 0.5, "evidence": []}, "non-empty"),
    ({"label": "none", "confidence": 1.5, "evidence": []}, "outside"),
    ({"label": "none", "confidence": -0.1, "evidence": []}, "outside"),
    ({"label": "none", "confidence": "high", "evidence": []}, "not numeric"),
    ({"label": "none", "confidence": True, "evidence": []}, "boolean"),
    ({"label": "none", "confidence": 0.5, "evidence": [{"source": "web", "span": "x"}]}, "source"),
    ({"label": "none", "confidence": 0.5, "evidence": [{"source": "student_answer", "span": ""}]}, "span"),
    ({"label": "none", "confidence": 0.5, "evidence": "not a list but a str is coerced", "extra": 1}, None),
])
def test_invalid_records(obj, msg):
    if msg is None:
        S.validate_record(obj, row_id="r", student_answer=ANSWER, labels=LABELS)  # coerced, no error
        return
    with pytest.raises(S.SchemaError, match=msg):
        S.validate_record(obj, row_id="r", student_answer=ANSWER, labels=LABELS)


def test_lenient_coercions_are_recorded_as_warnings():
    rec = S.validate_record({"label": "None", "confidence": "0.7", "evidence": ["find the node"]},
                            row_id="r", student_answer=ANSWER, labels=LABELS)
    assert rec.label == "none" and rec.confidence == 0.7
    assert rec.evidence[0].source == "student_answer" and rec.citation_valid
    assert len(rec.warnings) == 3


def test_parse_json_object_tolerates_fences_and_prose():
    assert S.parse_json_object('{"label": "none"}') == {"label": "none"}
    assert S.parse_json_object('```json\n{"label": "none"}\n```') == {"label": "none"}
    assert S.parse_json_object('Here you go: {"label": "none", "x": {"y": 1}} thanks') == {"label": "none", "x": {"y": 1}}
    with pytest.raises(S.SchemaError):
        S.parse_json_object("no json here")
    with pytest.raises(S.SchemaError):
        S.parse_json_object("[1, 2]")
    with pytest.raises(S.SchemaError):
        S.parse_json_object("")


def test_record_round_trip():
    rec = S.validate_record({"label": "other_error", "confidence": 0.4,
                             "evidence": [{"source": "student_answer", "span": "n log n"}]},
                            row_id="r1", student_answer=ANSWER, labels=LABELS, question_id="q")
    d = rec.to_dict()
    assert d["evidence"] == [{"source": "student_answer", "span": "n log n"}]
    assert S.Record.from_dict(d) == rec


def test_real_taxonomy_label_set():
    labels = S.label_set()
    assert len(labels) == 31
    assert labels[-3:] == ["none", "other_error", "insufficient_evidence"]
    assert "RCreturnIsRequired" in labels and len(set(labels)) == len(labels)
