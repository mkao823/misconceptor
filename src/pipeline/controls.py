"""Positive control for the Critic: authored cases, the arms they are run in, and the rates.

Specification: docs/CRITIC_SPEC.md, section 7. Cases live in configs/controls/<name>.yaml and
are authored control material: invented student answers, never rows of the eval sheet and
never Mohler answers. ``load_controls`` refuses a file that is not marked as authored.

A *dependent* case names the corpus chunks that carry the course-specific fact its judgement
turns on. It is run in two arms:

  withheld   every supporting chunk is withheld from the first retrieval only
  present    every supporting chunk is forced into the first-pass k

An *independent* case is run once (arm ``natural``) with condition 3's ordinary retrieval.

An arm is the first pass and one Critic call, made with the same functions the condition 4
loop is made of (``loop.first_pass_retrieval``, ``loop.diagnose``, ``critic.judge``,
``loop.requery``). "Triggered" means the verdict is ``sufficient: false``. When an arm
triggers, the re-query is run (no model call) to see which chunks it would bring; for a
withheld arm, "recovered" means those chunks include a withheld supporting chunk. No
re-diagnosis is made: the control is about the Critic's judgement, not about labels, and
nothing here is scored against a gold label.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.baselines import rag
from src.config import CONFIG_DIR, sha256_text
from src.pipeline import critic, loop
from src.retrieval import DEFAULT_K, Corpus, instructor_answer_chunk_id
from src.schema import SchemaError

CONTROL_DIR = CONFIG_DIR / "controls"
DEFAULT_CONTROLS = "critic_positive_control_v1"
IN_SCOPE_QUESTIONS = ("E03.Q06", "E03.Q07", "E05.Q03", "E05.Q04", "E10.Q07", "E12.Q10", "E11.Q09")
KINDS = ("dependent", "independent")
INDEPENDENT_KINDS = ("matches_reference", "vague", "plainly_wrong")
ARMS = {"dependent": ("withheld", "present"), "independent": ("natural",)}


@dataclass
class ControlSet:
    name: str
    path: str
    sha256: str
    provenance: str
    questions: dict
    cases: list[dict]

    @property
    def dependent(self) -> list[dict]:
        return [c for c in self.cases if c["kind"] == "dependent"]

    @property
    def independent(self) -> list[dict]:
        return [c for c in self.cases if c["kind"] == "independent"]


def load_controls(name: str = DEFAULT_CONTROLS, control_dir: Path = CONTROL_DIR, *,
                  corpus: Corpus | None = None,
                  required_questions: tuple[str, ...] = IN_SCOPE_QUESTIONS) -> ControlSet:
    """Load and check configs/controls/<name>.yaml.

    Refuses the file unless it and every case are marked as authored, ids are unique, every
    pair holds exactly one dependent and one independent case on the same question, every
    required question has a dependent case, and (when ``corpus`` is given) every supporting
    chunk exists and is not the question's own instructor-answer chunk, which condition 3
    never retrieves.
    """
    path = Path(control_dir) / f"{name}.yaml"
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or data.get("provenance") != "authored":
        raise SchemaError(f"{path.name}: top-level 'provenance: authored' is required; control cases must "
                          "be invented for the control, never copied from the eval sheet or Mohler")
    questions = data.get("questions") or {}
    cases = data.get("cases") or []
    if not cases:
        raise SchemaError(f"{path.name}: no cases")
    seen: set[str] = set()
    pairs: dict[str, list[dict]] = {}
    for case in cases:
        cid = case.get("id")
        if not cid or cid in seen:
            raise SchemaError(f"{path.name}: case ids must be present and unique (got {cid!r})")
        seen.add(cid)
        if case.get("authored") is not True:
            raise SchemaError(f"{path.name}: case {cid} is not marked 'authored: true'")
        if case.get("kind") not in KINDS:
            raise SchemaError(f"{path.name}: case {cid} kind {case.get('kind')!r} not in {KINDS}")
        qid = case.get("question_id")
        if qid not in questions:
            raise SchemaError(f"{path.name}: case {cid} question_id {qid!r} is not under 'questions'")
        for key in ("question", "instructor_answer"):
            if not (questions[qid] or {}).get(key):
                raise SchemaError(f"{path.name}: question {qid} has no {key}")
        if not str(case.get("student_answer") or "").strip() or not case.get("pair"):
            raise SchemaError(f"{path.name}: case {cid} needs a student_answer and a pair")
        if case["kind"] == "dependent":
            chunks = case.get("supporting_chunks") or []
            if not chunks or not case.get("fact"):
                raise SchemaError(f"{path.name}: dependent case {cid} needs a fact and supporting_chunks")
            if len(set(chunks)) != len(chunks):
                raise SchemaError(f"{path.name}: case {cid} lists a supporting chunk twice")
            if instructor_answer_chunk_id(qid) in chunks:
                raise SchemaError(f"{path.name}: case {cid} lists its own reference answer as a supporting chunk")
            if corpus is not None:
                unknown = [c for c in chunks if c not in corpus]
                if unknown:
                    raise SchemaError(f"{path.name}: case {cid} names unknown chunks {unknown}")
        elif case.get("independent_kind") not in INDEPENDENT_KINDS:
            raise SchemaError(f"{path.name}: independent case {cid} needs independent_kind in {INDEPENDENT_KINDS}")
        pairs.setdefault(case["pair"], []).append(case)
    for pair, members in pairs.items():
        kinds = sorted(c["kind"] for c in members)
        if kinds != ["dependent", "independent"] or len({c["question_id"] for c in members}) != 1:
            raise SchemaError(f"{path.name}: pair {pair} must hold one dependent and one independent case "
                              "on the same question")
    missing = [q for q in required_questions if q not in {c["question_id"] for c in cases if c["kind"] == "dependent"}]
    if missing:
        raise SchemaError(f"{path.name}: no dependent case for {missing}")
    return ControlSet(name=name, path=str(path), sha256=sha256_text(text),
                      provenance=str(data.get("source_statement") or data["provenance"]),
                      questions=questions, cases=cases)


def case_row(case: dict, controls: ControlSet) -> dict:
    """The case as a sheet-like row, so condition 3's code can diagnose it."""
    q = controls.questions[case["question_id"]]
    return {"id": case["id"], "question_id": case["question_id"], "question": q["question"],
            "instructor_answer": q["instructor_answer"],
            "student_answer": " ".join(str(case["student_answer"]).split())}


def arm_retrieval_args(case: dict, arm: str) -> dict:
    if arm not in ARMS[case["kind"]]:
        raise ValueError(f"case {case['id']} ({case['kind']}) has no arm {arm!r}")
    if arm == "withheld":
        return {"first_pass_exclude": list(case["supporting_chunks"])}
    if arm == "present":
        return {"first_pass_force": list(case["supporting_chunks"])}
    return {}


def run_arm(case: dict, arm: str, controls: ControlSet, client, ctx: loop.Context, *, k: int = DEFAULT_K,
            **settings) -> dict:
    """First pass and one Critic call for ``case`` in ``arm``; returns the arm's log entry."""
    row = case_row(case, controls)
    supporting = list(case.get("supporting_chunks") or [])
    rc = loop.RecordingClient(client)
    hits, withheld, first_only = loop.first_pass_retrieval(row, ctx.retriever, k=k, **arm_retrieval_args(case, arm))
    natural, _ = rag.retrieve_for_row(row, ctx.retriever, k=k)
    natural_ids = [h.chunk.id for h in natural]
    shown_ids = [h.chunk.id for h in hits]
    out = {"case": case["id"], "pair": case["pair"], "question_id": case["question_id"], "kind": case["kind"],
           "independent_kind": case.get("independent_kind"), "arm": arm,
           "supporting_chunks": supporting,
           "supporting_in_natural_top_k": [c for c in supporting if c in natural_ids],
           "chunk_ids_shown": shown_ids, "first_pass_withheld_chunk_ids": first_only,
           "draft": None, "critic": None, "triggered": None, "requery": None, "recovered": None,
           "error": None}

    def close() -> dict:
        out["tokens"] = loop.sum_tokens(rc.calls)
        out["n_calls"] = len(rc.calls)
        out["calls"] = rc.calls
        return out

    rc.tag(0, "diagnosis")
    record, err = loop.diagnose(row, hits, ctx, rc, extra_meta=rag.retrieval_meta(hits, withheld + first_only),
                                **settings)
    if record is None:
        out["error"] = {"where": "first_pass", "stage": err["stage"], "error": err["error"]}
        return close()
    out["draft"] = {"label": record.label, "confidence": record.confidence,
                    "evidence": [{"source": e.source, "span": e.span} for e in record.evidence],
                    "citation_valid": record.citation_valid}
    rc.tag(0, "critic")
    verdict, info = critic.judge(row, rc, ctx.critic_template, hits, record, ctx.taxonomy, **settings)
    if verdict is None:
        out["error"] = {"where": "critic", "stage": info.get("stage"), "error": info.get("error")}
        return close()
    out["critic"] = verdict.to_log()
    out["triggered"] = not verdict.sufficient
    if out["triggered"]:
        new_hits = loop.requery(verdict.query, ctx.retriever, shown_ids, withheld, k)
        new_ids = [h.chunk.id for h in new_hits]
        out["requery"] = {"query": verdict.query, "retrieved": [h.to_log() for h in new_hits],
                          "new_chunk_ids": new_ids}
        if arm == "withheld":
            got = [c for c in supporting if c in new_ids]
            out["recovered"] = {"chunk_ids": got, "any": bool(got), "all": len(got) == len(supporting)}
    return close()


# -- rates ---------------------------------------------------------------------------------

def _rate(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def summarize(arms: list[dict]) -> dict:
    """Trigger rates per arm and recovery of withheld chunks, each with its counts.

    A rate's denominator is the number of arms that produced a Critic verdict; arms where the
    first pass or the Critic failed are counted under ``n_errors`` and are in no rate.
    """
    out: dict = {"arms": {}}
    for arm in ("withheld", "present", "natural"):
        mine = [a for a in arms if a["arm"] == arm]
        judged = [a for a in mine if a["triggered"] is not None]
        n_trig = sum(1 for a in judged if a["triggered"])
        out["arms"][arm] = {"n": len(mine), "n_judged": len(judged), "n_errors": len(mine) - len(judged),
                            "n_triggered": n_trig, "trigger_rate": _rate(n_trig, len(judged))}
    natural = [a for a in arms if a["arm"] == "natural" and a["triggered"] is not None]
    out["natural_by_kind"] = {}
    for kind in INDEPENDENT_KINDS:
        mine = [a for a in natural if a.get("independent_kind") == kind]
        if mine:
            out["natural_by_kind"][kind] = {"n_judged": len(mine), "n_triggered": sum(1 for a in mine if a["triggered"])}
    triggered_withheld = [a for a in arms if a["arm"] == "withheld" and a["triggered"]]
    n_any = sum(1 for a in triggered_withheld if a["recovered"] and a["recovered"]["any"])
    n_all = sum(1 for a in triggered_withheld if a["recovered"] and a["recovered"]["all"])
    n_withheld_judged = out["arms"]["withheld"]["n_judged"]
    out["recovery"] = {"n_withheld_triggered": len(triggered_withheld),
                       "n_recovered_any": n_any, "n_recovered_all": n_all,
                       "rate_any_given_triggered": _rate(n_any, len(triggered_withheld)),
                       "rate_any_over_withheld_judged": _rate(n_any, n_withheld_judged)}
    # paired view: per dependent case, did the Critic trigger with the chunk withheld and not with it present?
    by_case: dict[str, dict] = {}
    for a in arms:
        if a["arm"] in ("withheld", "present"):
            by_case.setdefault(a["case"], {})[a["arm"]] = a["triggered"]
    complete = {c: v for c, v in by_case.items() if v.get("withheld") is not None and v.get("present") is not None}
    out["paired"] = {
        "n_cases_both_arms_judged": len(complete),
        "n_withheld_only": sum(1 for v in complete.values() if v["withheld"] and not v["present"]),
        "n_both": sum(1 for v in complete.values() if v["withheld"] and v["present"]),
        "n_neither": sum(1 for v in complete.values() if not v["withheld"] and not v["present"]),
        "n_present_only": sum(1 for v in complete.values() if not v["withheld"] and v["present"]),
    }
    n_calls = sum(a["n_calls"] for a in arms)
    total = sum(a["tokens"]["total_tokens"] for a in arms)
    out["cost"] = {"n_arms": len(arms), "n_calls": n_calls, "total_tokens": total,
                   "mean_tokens_per_arm": round(total / len(arms), 1) if arms else None,
                   "mean_calls_per_arm": round(n_calls / len(arms), 2) if arms else None}
    return out


def _frac(n: int, d: int) -> str:
    return f"{n}/{d}" + (f" ({n / d:.0%})" if d else "")


def summary_markdown(summary: dict, arms: list[dict], header: dict) -> str:
    """The short report written next to the arm log."""
    a = summary["arms"]
    rec = summary["recovery"]
    pair = summary["paired"]
    lines = [
        f"# Critic positive control: {header['run_id']}", "",
        f"Model `{header['model']}`, controls `{header['controls']}` ({header['n_cases']} authored cases: "
        f"{header['n_dependent']} dependent, {header['n_independent']} non-dependent), Critic template "
        f"`{header['critic_template']}`, k = {header['k']}, {header['timestamp']}.", "",
        "The cases are authored control material, not eval rows, and carry no gold label. The rates below "
        "describe how the Critic behaved on these constructed cases. They are not evidence for or against "
        "the mechanism claim.", "",
        "\"Triggered\" means the Critic returned `sufficient: false` on the first-pass draft. Rates are over "
        "arms that produced a verdict.", "",
        "| Arm | Triggered | Errors |", "|---|---|---|",
        f"| Dependent case, supporting chunk withheld from the first retrieval | "
        f"{_frac(a['withheld']['n_triggered'], a['withheld']['n_judged'])} | {a['withheld']['n_errors']} |",
        f"| Dependent case, supporting chunk present in the first retrieval | "
        f"{_frac(a['present']['n_triggered'], a['present']['n_judged'])} | {a['present']['n_errors']} |",
        f"| Non-dependent case, ordinary retrieval | "
        f"{_frac(a['natural']['n_triggered'], a['natural']['n_judged'])} | {a['natural']['n_errors']} |", "",
    ]
    if summary["natural_by_kind"]:
        parts = [f"{kind} {v['n_triggered']}/{v['n_judged']}" for kind, v in summary["natural_by_kind"].items()]
        lines += ["Non-dependent cases by kind (triggered / judged): " + ", ".join(parts) + ".", ""]
    lines += [
        f"Recovery: of the {rec['n_withheld_triggered']} withheld arms that triggered, the re-query's k chunks "
        f"contained a withheld supporting chunk in {rec['n_recovered_any']} "
        f"(all of the withheld chunks in {rec['n_recovered_all']}). Over all "
        f"{a['withheld']['n_judged']} judged withheld arms that is {_frac(rec['n_recovered_any'], a['withheld']['n_judged'])}.", "",
        f"Paired view over the {pair['n_cases_both_arms_judged']} dependent cases judged in both arms: triggered "
        f"only when withheld {pair['n_withheld_only']}, in both arms {pair['n_both']}, in neither "
        f"{pair['n_neither']}, only when present {pair['n_present_only']}.", "",
        f"Cost: {summary['cost']['n_arms']} arms, {summary['cost']['n_calls']} model calls, "
        f"{summary['cost']['total_tokens']} tokens ({summary['cost']['mean_tokens_per_arm']} tokens and "
        f"{summary['cost']['mean_calls_per_arm']} calls per arm, cache hits included).", "",
        "## Arms", "",
        "| Case | Question | Arm | Draft label | Triggered | Critic's query | Re-query chunks | Recovered |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm in arms:
        if arm["error"]:
            lines.append(f"| {arm['case']} | {arm['question_id']} | {arm['arm']} | "
                         f"{(arm['draft'] or {}).get('label', '')} | ERROR ({arm['error']['where']}) | | | |")
            continue
        rq = arm["requery"] or {}
        recovered = ""
        if arm["arm"] == "withheld" and arm["triggered"]:
            recovered = ", ".join(f"`{c}`" for c in arm["recovered"]["chunk_ids"]) or "no"
        query = (rq.get("query") or "").replace("|", "/")
        lines.append(f"| {arm['case']} | {arm['question_id']} | {arm['arm']} | {arm['draft']['label']} | "
                     f"{'yes' if arm['triggered'] else 'no'} | {query} | "
                     f"{', '.join(f'`{c}`' for c in rq.get('new_chunk_ids', []))} | {recovered} |")
    lines += ["", "## What the Critic said was missing", ""]
    said = [arm for arm in arms if arm["triggered"]]
    if not said:
        lines.append("No arm triggered.")
    for arm in said:
        lines.append(f"- {arm['case']} ({arm['arm']}): {arm['critic']['missing']}")
    lines += ["", "Withheld chunks per dependent case (and whether ordinary retrieval would have shown them):", ""]
    for arm in arms:
        if arm["arm"] == "withheld":
            natural = set(arm["supporting_in_natural_top_k"])
            lines.append(f"- {arm['case']}: " + ", ".join(
                f"`{c}` ({'in' if c in natural else 'not in'} the ordinary top k)" for c in arm["supporting_chunks"]))
    return "\n".join(lines) + "\n"
