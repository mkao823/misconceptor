"""Condition 4: condition 3 plus Critic-driven, insufficiency-triggered re-retrieval.

Specification: docs/CRITIC_SPEC.md. In short, per row:

  round 0   condition 3, unchanged (same retrieval, template, taxonomy text, few-shot examples,
            temperature 0, seed, repair round-trip, through condition 3's own functions);
            its validated record is the draft
  loop      Critic verdict on the draft (src/pipeline/critic.py). If "insufficient": retrieve
            k new chunks with the Critic's query, never re-showing a chunk, and diagnose again
            with all accumulated chunks. At most ``max_rounds`` such refinement rounds.
  stop      round_limit | sufficient | no_new_chunks | critic_error | rediagnosis_error

The only difference from condition 3 is this loop: diagnoses are rendered by
``taxonomy_fewshot.render_messages`` and run by ``direct.complete_and_validate``, and with
``max_rounds=0`` the Critic is never called and the output equals condition 3's.

``run_row`` returns the final validated record (or an error dict when the first pass fails)
and a ``trace`` with one entry per round and one entry per model call. A row's tokens are
the sum over every call: diagnoses, Critic calls and repairs of either.

``first_pass_exclude`` and ``first_pass_force`` exist for the positive control
(scripts/run_positive_control.py): chunk ids withheld from, or forced into, the first
retrieval only. A normal condition 4 run leaves both empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.baselines import rag, taxonomy_fewshot
from src.baselines.direct import PromptTemplate, complete_and_validate
from src.baselines.taxonomy_fewshot import FewShotSet
from src.pipeline import critic
from src.retrieval import DEFAULT_K, Hit, Retriever, build_query
from src.schema import Record

CONDITION = 4
NAME = "critic_loop"
DEFAULT_TEMPLATE = taxonomy_fewshot.DEFAULT_TEMPLATE          # the diagnosis template is condition 3's
DEFAULT_CRITIC_TEMPLATE = critic.DEFAULT_TEMPLATE
DEFAULT_MAX_ROUNDS = 2
STOP_REASONS = ("round_limit", "sufficient", "no_new_chunks", "critic_error", "rediagnosis_error",
                "first_pass_error")
GENERATION_KEYS = ("temperature", "seed", "max_tokens", "json_mode", "max_repairs")


@dataclass
class Context:
    """Everything a row needs that does not change between rows."""
    template: PromptTemplate            # condition 3's diagnosis template
    critic_template: PromptTemplate
    labels: list[str]
    retriever: Retriever
    taxonomy: dict
    fewshot: FewShotSet
    taxonomy_text: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.taxonomy_text:
            self.taxonomy_text = taxonomy_fewshot.taxonomy_text(self.taxonomy)


class RecordingClient:
    """Wraps an LLMClient and logs the usage of every ``chat`` call, tagged with round and role."""

    def __init__(self, client):
        self.client = client
        self.calls: list[dict] = []
        self._round = 0
        self._role = "diagnosis"

    def tag(self, round: int, role: str) -> None:   # noqa: A002 - "round" is the spec's word
        self._round, self._role = round, role

    def chat(self, messages: list[dict], **kwargs):
        resp = self.client.chat(messages, **kwargs)
        attempt = 1 + sum(1 for c in self.calls if (c["round"], c["role"]) == (self._round, self._role))
        self.calls.append({"round": self._round, "role": self._role, "attempt": attempt,
                           "prompt_tokens": resp.usage.prompt_tokens,
                           "completion_tokens": resp.usage.completion_tokens,
                           "total_tokens": resp.usage.total_tokens, "cached": resp.cached})
        return resp


def sum_tokens(calls: Iterable[dict]) -> dict:
    calls = list(calls)
    p = sum(c["prompt_tokens"] for c in calls)
    c_ = sum(c["completion_tokens"] for c in calls)
    return {"prompt_tokens": p, "completion_tokens": c_, "total_tokens": p + c_}


# -- retrieval ---------------------------------------------------------------------

def first_pass_retrieval(row: dict, retriever: Retriever, *, k: int = DEFAULT_K, exclude: Iterable[str] = (),
                         keep_own_reference: bool = False, first_pass_exclude: Iterable[str] = (),
                         first_pass_force: Iterable[str] = ()) -> tuple[list[Hit], list[str], list[str]]:
    """Return (hits, chunk ids withheld in every round, chunk ids withheld in the first pass only).

    With ``first_pass_exclude`` and ``first_pass_force`` empty this is exactly condition 3's
    retrieval (``rag.retrieve_for_row``). ``first_pass_force`` puts the named chunks into the
    first-pass k: they take the place of the lowest-ranked hits, and the k chunks are listed
    by score (a forced chunk that does not match the query at all comes last).
    """
    exclude = list(dict.fromkeys(exclude))
    first_only = [c for c in dict.fromkeys(first_pass_exclude) if c not in exclude]
    force = list(dict.fromkeys(first_pass_force))
    hits, withheld = rag.retrieve_for_row(row, retriever, k=k, exclude=exclude + first_only,
                                          keep_own_reference=keep_own_reference)
    always = [c for c in withheld if c not in first_only]
    if force:
        clash = sorted(set(force) & set(withheld))
        if clash:
            raise ValueError(f"cannot force chunks that are withheld: {clash}")
        if len(force) > k:
            raise ValueError(f"cannot force {len(force)} chunks into k={k}")
        ranked = retriever.retrieve(build_query(row), len(retriever.corpus), withheld)
        by_id = {h.chunk.id: h for h in ranked}
        forced = [by_id[c] if c in by_id else Hit(chunk=retriever.corpus.get(c), score=0.0, rank=0) for c in force]
        rest = [h for h in ranked if h.chunk.id not in set(force)][: k - len(forced)]
        order = {cid: i for i, cid in enumerate(retriever.corpus.ids())}
        chosen = sorted(forced + rest, key=lambda h: (-h.score, order[h.chunk.id]))
        hits = [Hit(chunk=h.chunk, score=h.score, rank=i) for i, h in enumerate(chosen, 1)]
    return hits, always, first_only


def requery(query: str, retriever: Retriever, shown_ids: Iterable[str], withheld: Iterable[str],
            k: int = DEFAULT_K) -> list[Hit]:
    """Up to k chunks for the Critic's query, never one already shown or withheld for the row."""
    return retriever.retrieve(query, k, [*withheld, *shown_ids])


# -- diagnosis (condition 3's code) -----------------------------------------------------

def shown_log(hits: list[Hit], rounds: list[int]) -> list[dict]:
    return [{**h.to_log(), "round": r} for h, r in zip(hits, rounds)]


def diagnose(row: dict, hits: list[Hit], ctx: Context, client, *, extra_meta: dict | None = None,
             **settings) -> tuple[Record | None, dict | None]:
    """One condition 3 diagnosis of ``row`` with ``hits`` as the retrieved material."""
    messages = taxonomy_fewshot.render_messages(ctx.template, row, hits, ctx.taxonomy, ctx.fewshot)
    return complete_and_validate(row, client, messages, ctx.labels,
                                 retrieved_chunks=[h.chunk.text for h in hits],
                                 taxonomy_text=ctx.taxonomy_text, extra_meta=extra_meta, **settings)


def _draft_log(record: Record) -> dict:
    return {"label": record.label, "confidence": record.confidence, "citation_valid": record.citation_valid,
            "attempts": record.meta.get("attempts")}


# -- the loop ------------------------------------------------------------------------

def run_row(row: dict, client, ctx: Context, *, k: int = DEFAULT_K, max_rounds: int = DEFAULT_MAX_ROUNDS,
            exclude: Iterable[str] = (), keep_own_reference: bool = False,
            first_pass_exclude: Iterable[str] = (), first_pass_force: Iterable[str] = (),
            **settings) -> tuple[Record | None, dict | None, dict]:
    """Condition 4 for one row: (record, None, trace) or, when the first pass fails, (None, error, trace).

    ``settings`` are the generation settings of ``complete_and_validate`` (temperature, seed,
    max_tokens, json_mode, max_repairs); the Critic is called with the same ones.
    """
    if max_rounds < 0:
        raise ValueError("max_rounds must be >= 0")
    unknown = set(settings) - set(GENERATION_KEYS)
    if unknown:
        raise TypeError(f"unknown generation settings {sorted(unknown)}")
    rc = RecordingClient(client)
    hits, withheld, first_only = first_pass_retrieval(
        row, ctx.retriever, k=k, exclude=exclude, keep_own_reference=keep_own_reference,
        first_pass_exclude=first_pass_exclude, first_pass_force=first_pass_force)
    shown: list[Hit] = list(hits)
    shown_round: list[int] = [0] * len(hits)
    rounds: list[dict] = []

    def open_round(number: int, query: str, source: str, new_hits: list[Hit]) -> dict:
        entry = {"round": number, "query": query, "query_source": source,
                 "retrieved": [h.to_log() for h in new_hits],
                 "new_chunk_ids": [h.chunk.id for h in new_hits],
                 "chunk_ids_shown": [h.chunk.id for h in shown],
                 "draft": None, "critic": None}
        rounds.append(entry)
        return entry

    def meta_for_round() -> dict:
        # round 0 logs exactly what condition 3 logs, plus the round of each chunk
        return {"retrieved": shown_log(shown, shown_round), "withheld_chunk_ids": list(withheld + first_only)}

    def finish(stop_reason: str, first_label: str | None, final: Record | None, n_refinements: int) -> dict:
        for entry in rounds:
            # a round's calls: its diagnosis (and repairs) and the Critic's verdict on its draft
            mine = [c for c in rc.calls if c["round"] == entry["round"]]
            entry["tokens"] = sum_tokens(mine)
            entry["calls"] = len(mine)
        return {"max_rounds": max_rounds, "k": k, "stop_reason": stop_reason, "n_refinements": n_refinements,
                "n_calls": len(rc.calls), "tokens": sum_tokens(rc.calls),
                "first_call_tokens": rc.calls[0]["total_tokens"] if rc.calls else 0,
                "first_pass_label": first_label, "final_label": final.label if final is not None else None,
                "critic_triggered": bool(rounds and rounds[0]["critic"] and rounds[0]["critic"].get("sufficient") is False),
                "withheld_chunk_ids": list(withheld), "first_pass_withheld_chunk_ids": list(first_only),
                "first_pass_forced_chunk_ids": list(dict.fromkeys(first_pass_force)),
                "rounds": rounds, "calls": rc.calls}

    # round 0: condition 3
    entry = open_round(0, build_query(row), "row", hits)
    rc.tag(0, "diagnosis")
    record, err = diagnose(row, shown, ctx, rc, extra_meta=meta_for_round(), **settings)
    if record is None:
        entry["draft_error"] = {"stage": err["stage"], "error": err["error"]}
        trace = finish("first_pass_error", None, None, 0)
        err.update({"usage": {"prompt_tokens": trace["tokens"]["prompt_tokens"],
                              "completion_tokens": trace["tokens"]["completion_tokens"]},
                    "n_calls": trace["n_calls"], "trace": trace})
        return None, err, trace
    entry["draft"] = _draft_log(record)
    draft = record
    first_label = record.label
    started = 0            # refinement rounds started (a re-query that returned new chunks)
    refined = 0            # refinement rounds that produced a valid new draft

    while True:
        if started >= max_rounds:
            stop = "round_limit"
            break
        rc.tag(started, "critic")
        verdict, info = critic.judge(row, rc, ctx.critic_template, shown, draft, ctx.taxonomy, **settings)
        if verdict is None:
            entry["critic"] = {"sufficient": None, "missing": "", "query": "", "stage": info.get("stage"),
                               "error": info.get("error"), "attempts": info["attempts"]}
            stop = "critic_error"
            break
        entry["critic"] = {**verdict.to_log(), "attempts": info["attempts"]}
        if verdict.sufficient:
            stop = "sufficient"
            break
        new_hits = requery(verdict.query, ctx.retriever, [h.chunk.id for h in shown], withheld, k)
        if not new_hits:
            open_round(started + 1, verdict.query, "critic", [])       # logged; no diagnosis is made
            stop = "no_new_chunks"
            break
        started += 1
        shown.extend(new_hits)
        shown_round.extend([started] * len(new_hits))
        entry = open_round(started, verdict.query, "critic", new_hits)
        rc.tag(started, "diagnosis")
        record, err = diagnose(row, shown, ctx, rc, extra_meta=meta_for_round(), **settings)
        if record is None:
            entry["draft_error"] = {"stage": err["stage"], "error": err["error"]}
            stop = "rediagnosis_error"                                  # the previous valid draft stands
            break
        entry["draft"] = _draft_log(record)
        draft = record
        refined += 1

    trace = finish(stop, first_label, draft, refined)
    draft.meta.update({
        "prompt_tokens": trace["tokens"]["prompt_tokens"],          # row totals over every call
        "completion_tokens": trace["tokens"]["completion_tokens"],
        "n_calls": trace["n_calls"], "cached": all(c["cached"] for c in rc.calls),
        "stop_reason": stop, "n_refinements": refined, "first_pass_label": first_label,
        "critic_triggered": trace["critic_triggered"],
    })
    return draft, None, trace


def to_prediction(record: Record, trace: dict) -> dict:
    """The predictions.jsonl line: the usual record plus ``trace``."""
    return {**record.to_dict(), "trace": trace}
