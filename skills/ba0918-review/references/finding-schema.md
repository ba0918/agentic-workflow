# Finding shape

One JSON file per branch holds the current state of every finding and of cycle's assumption-check
attempts (a snapshot that is overwritten, never an append-only log). Only cycle writes it. Reviewers return arrays of
findings in the same shape, without `id`, `status`, `commits`, or `evaluations`; the caller
fills those.

```json
{
  "base": "<commit the full review diffs from>",
  "last_reviewed_head": "<branch head at the previous review>",
  "assumption_attempts": [
    {
      "round": 5,
      "condition": "new visible finding near the fix, twice",
      "base": "<comparison base at the time of the attempt>",
      "stack": [
        {"assumption": "one sentence, the level others rest on", "lives_in": "specification"},
        {"assumption": "one sentence, where the last fix touched", "lives_in": "implementation"}
      ],
      "replaced": "the assumption swapped",
      "replacement": "what replaced it",
      "sent_to": "fixer"
    }
  ],
  "findings": [
    {
      "id": 7,
      "severity": "critical",
      "action": "fix_and_verify",
      "provisional_answer": {
        "answer": "the answer chosen, with the strongest grounds",
        "overturned_if": "what the person would say to overturn it"
      },
      "profile": "Code",
      "perspective": "quality",
      "claim": "one-sentence statement of the problem",
      "evidence": [
        {"path": "src/x.py", "lines": "40-58", "summary": "what was observed"}
      ],
      "oracle": {
        "proposal": "pytest tests/test_x.py::test_rejects_empty",
        "measured": "fails_now",
        "note": "fails because the test does not exist yet; or why not run; or why no machine can check it and what a person reads to confirm"
      },
      "status": {"state": "open", "closed_reason": null},
      "commits": [],
      "evaluations": [{"round": 2, "verdict": "still_present"}]
    }
  ]
}
```

| Key | Values |
|---|---|
| `severity` | `security` / `critical` / `warn` / `info`; the caller changes a finding that states no defect to `warn` |
| `action` | `auto_fix` / `fix_and_verify` / `record_only` (reviewer proposal; caller decides) |
| `provisional_answer` | only on a finding whose fix needs a judgment about meaning; `answer` and `overturned_if` (reviewer proposal; caller decides). Omitted otherwise |
| `profile` | `Code` / `Document` / `Skill` |
| `perspective` | `quality` / `conformance` |
| `oracle.measured` | `fails_now` / `not_run` (unsafe; reason in note) / `not_applicable` (`info`, or no machine can check it; reason and the points a person reads in note) |
| `status.state` | `open` / `closed`; `closed_reason` is `fixed` or `accepted` |
| `commits` | commit hashes the fixer reported for this finding |
| `evaluations` | one per review that evaluated this finding, with the round-trip number: `{"round": n, "verdict": "still_present" \| "no_longer_visible"}`; a full-review match appends `still_present` |
| `assumption_attempts` | one per assumption check cycle ran: the round and condition that triggered it, the comparison base then, the stack top-first with `lives_in` `implementation` / `plan` / `specification`, the swapped assumption and its replacement, and `sent_to` `fixer` or `ended`. No per-fix record is kept: which commits addressed which finding lives on the finding |

Diff-review return shape: `{"verdicts": [{"id": 7, "verdict": "still_present"}], "new": [ ...findings... ]}`.
