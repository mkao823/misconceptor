from src.baselines import keyword as K
from src.schema import label_set, load_taxonomy

TAX = {
    "items": [
        {"id": "ItemA", "trigger_phrases": ["n log n", "nlogn"]},
        {"id": "ItemB", "trigger_phrases": ["n/2", "half the nodes"]},
        {"id": "ItemC", "trigger_phrases": ["one operation", "1 operation", "two elements"]},
        {"id": "ItemD", "trigger_phrases": [], "no_trigger_phrases_reason": "residual"},
    ],
    "special_labels": [{"id": "none"}, {"id": "other_error"}, {"id": "insufficient_evidence"}],
}
ROWS = [
    {"id": "s1", "question_id": "q", "student_answer": "It takes N LOG N   comparisons, I think.", "score_avg": "1.0"},
    {"id": "s2", "question_id": "q", "student_answer": "The height of the tree, log n.", "score_avg": "5.0"},
    # tie: ItemA (n log n) and ItemB (n/2) each match one phrase -> earlier item wins
    {"id": "s3", "question_id": "q", "student_answer": "either n/2 or n log n", "score_avg": "0.5"},
]


def test_three_synthetic_answers():
    recs = K.run(ROWS, TAX)
    assert [r.label for r in recs] == ["ItemA", "none", "ItemA"]
    # evidence is the verbatim slice of the (whitespace-normalized) answer, so citations are valid
    assert recs[0].evidence[0].span == "N LOG N" and recs[0].citation_valid
    assert recs[0].confidence == 1.0
    assert recs[1].evidence == [] and recs[1].confidence == 0.5
    assert recs[2].confidence == 0.5 and recs[2].meta["matches"] == {"ItemA": ["n log n"], "ItemB": ["n/2"]}


def test_most_distinct_phrases_wins_and_score_is_ignored():
    rows = [{"id": "x", "question_id": "q", "student_answer": "one operation on two elements; n/2", "score_avg": "5.0"},
            {"id": "y", "question_id": "q", "student_answer": "one operation on two elements; n/2", "score_avg": "0.0"}]
    recs = K.run(rows, TAX)
    assert recs[0].label == recs[1].label == "ItemC"
    assert recs[0].confidence == recs[1].confidence == round(2 / 3, 4)


def test_real_taxonomy_runs_and_cites_verbatim():
    tax = load_taxonomy()
    rows = [{"id": "r", "question_id": "E10.Q07", "student_answer": "At most n/2 comparisons, half the nodes."},
            {"id": "e", "question_id": "E10.Q07", "student_answer": ""}]
    recs = K.run(rows, tax)
    assert recs[0].label == "BOsearchLinearScan" and recs[0].citation_valid
    assert recs[1].label == "none"
    assert all(r.label in label_set(tax) for r in recs)
