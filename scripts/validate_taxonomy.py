"""Sanity-check taxonomy/recursion_bigO.yaml.

Asserts that the file loads with yaml.safe_load, that every item carries the
required fields with allowed values, and that every id (taxonomy items plus
special_labels) is unique. Exit code 0 means the taxonomy is usable.

Usage:
    python scripts/validate_taxonomy.py [path/to/taxonomy.yaml]
"""

import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT = REPO_ROOT / "taxonomy" / "recursion_bigO.yaml"

REQUIRED = ["id", "concept", "source", "description", "kind", "observable_in", "trigger_phrases", "status"]
CONCEPTS = {"recursion", "big_o"}
KINDS = {"misconception", "difficulty", "mental_model"}
OBSERVABLE = {"code_tracing", "code_writing", "conceptual_recall"}
STATUSES = {"verified", "provisional"}
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def check(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    with open(path) as f:
        tax = yaml.safe_load(f)
    check(isinstance(tax, dict), "top level must be a mapping", errors)
    items = tax.get("items") if isinstance(tax, dict) else None
    specials = tax.get("special_labels") if isinstance(tax, dict) else None
    check(isinstance(items, list) and items, "`items` must be a non-empty list", errors)
    check(isinstance(specials, list) and specials, "`special_labels` must be a non-empty list", errors)
    if errors:
        return errors

    for i, it in enumerate(items):
        where = f"items[{i}] ({it.get('id', '?') if isinstance(it, dict) else '?'})"
        if not isinstance(it, dict):
            errors.append(f"{where}: not a mapping")
            continue
        missing = [k for k in REQUIRED if k not in it or it[k] in (None, "")]
        check(not missing, f"{where}: missing fields {missing}", errors)
        check(ID_RE.match(str(it.get("id", ""))) is not None, f"{where}: id must match {ID_RE.pattern}", errors)
        check(it.get("concept") in CONCEPTS, f"{where}: concept must be one of {sorted(CONCEPTS)}", errors)
        check(it.get("kind") in KINDS, f"{where}: kind must be one of {sorted(KINDS)}", errors)
        check(it.get("status") in STATUSES, f"{where}: status must be one of {sorted(STATUSES)}", errors)
        obs = it.get("observable_in") or []
        check(isinstance(obs, list) and obs and set(obs) <= OBSERVABLE,
              f"{where}: observable_in must be a non-empty subset of {sorted(OBSERVABLE)}", errors)
        tp = it.get("trigger_phrases")
        if tp == [] and it.get("no_trigger_phrases_reason"):
            pass  # residual categories may opt out of the keyword baseline, with a stated reason
        else:
            check(isinstance(tp, list) and 3 <= len(tp) <= 6 and all(isinstance(p, str) and p.strip() for p in tp),
                  f"{where}: trigger_phrases must be 3 to 6 non-empty strings "
                  f"(or [] with no_trigger_phrases_reason)", errors)
        check(isinstance(it.get("source"), str) and "http" in it.get("source", ""),
              f"{where}: source must be a citation string containing a URL", errors)

    for i, sp in enumerate(specials):
        where = f"special_labels[{i}]"
        check(isinstance(sp, dict) and sp.get("id") and sp.get("definition"),
              f"{where}: needs `id` and `definition`", errors)

    ids = [it.get("id") for it in items if isinstance(it, dict)] + \
          [sp.get("id") for sp in specials if isinstance(sp, dict)]
    dupes = [k for k, n in Counter(ids).items() if n > 1]
    check(not dupes, f"duplicate ids: {dupes}", errors)
    return errors


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    errors = validate(path)
    if errors:
        print(f"FAIL {path}:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    with open(path) as f:
        tax = yaml.safe_load(f)
    items = tax["items"]
    by = lambda key: dict(sorted(Counter(it[key] for it in items).items()))  # noqa: E731
    print(f"OK {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}: "
          f"{len(items)} items + {len(tax['special_labels'])} special labels, all ids unique")
    print(f"  by concept: {by('concept')}")
    print(f"  by kind:    {by('kind')}")
    print(f"  by status:  {by('status')}")


if __name__ == "__main__":
    main()
