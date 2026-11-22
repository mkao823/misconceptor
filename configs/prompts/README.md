# configs/prompts/

Versioned prompt templates. One file per template; never edit a template in
place once a run has used it. Copy it to a new version (`direct_v2.txt`) instead.
Every run manifest records the template name and the SHA-256 of its full text.

Format: the text before the first line that is exactly `---` is the system
message; the text after it is the user message. Placeholders use
`string.Template` syntax (`$question`, `$instructor_answer`, `$student_answer`,
`$label_ids`), so literal braces in JSON examples need no escaping.

| Template | Condition | Notes |
|---|---|---|
| `direct_v1.txt` | 1 (direct LLM) | Zero-shot. Lists only the allowed label ids and the three special labels; no taxonomy descriptions, no retrieval, no examples. |
