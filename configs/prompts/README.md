# configs/prompts/

Versioned prompt templates. One file per template; never edit a template in
place once a run has used it. Copy it to a new version (`direct_v2.txt`) instead.
Every run manifest records the template name and the SHA-256 of its full text.

Format: the text before the first line that is exactly `---` is the system
message; the text after it is the user message. Placeholders use
`string.Template` syntax (`$question`, `$instructor_answer`, `$student_answer`,
`$label_ids`, and for conditions 2 and 3 `$retrieved_chunks`, `$taxonomy_items`,
`$special_labels`, `$fewshot_examples`), so literal braces in JSON examples need
no escaping.

| File | Condition | Notes |
|---|---|---|
| `direct_v1.txt` | 1 (direct LLM) | Zero-shot. Lists only the allowed label ids and the three special labels; no taxonomy descriptions, no retrieval, no examples. |
| `rag_v1.txt` | 2 (+ course-material RAG) | `direct_v1` plus the top-k chunks retrieved from `data/corpus/` and permission to cite `retrieved` spans. Still label ids only: no taxonomy descriptions, no examples. |
| `taxonomy_fewshot_v1.txt` | 3 (+ taxonomy and few-shot) | `rag_v1` with the id list replaced by the full taxonomy text (id, concept, description and notes of every item, and the three special-label definitions, rendered from `taxonomy/recursion_bigO.yaml` at run time) and the examples in `fewshot_v1.yaml`. The static part comes first so the server can reuse its prompt cache across rows. May cite `retrieved` and `taxonomy` spans. |
| `fewshot_v1.yaml` | 3 | Eight **authored** examples (`provenance: authored`, `authored: true` on each): written for the prompt, on questions that are not among the seven in-scope ones, never taken from the eval sheet or from any Mohler answer. Covers `none`, `other_error`, `insufficient_evidence`, three Big-O items and two recursion items. The loader refuses a file that is not marked as authored, and the tests check the examples against the pilot sheet and the raw Mohler answers. The `rationale` field is for maintainers and is not shown to the model. The manifest records this file's name and SHA-256 under `fewshot`. |

Cited evidence is checked after whitespace normalization only: a span must be a
verbatim substring of the student answer, of one retrieved chunk shown for that
row, or of the taxonomy text shown. The row's reference answer is not a retrieved
excerpt, so quoting it as `retrieved` evidence is flagged.
