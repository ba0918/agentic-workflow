# Direct call

Read when a person called review directly, after the findings are verified and before the
report is handed over.

On a direct call, fix the `confirmed` findings whose action is `auto_fix` or `fix_and_verify`
without asking, before handing the report over; the report says what was fixed, why, and the
checks run afterwards. `record_only`, `unmeasured`, and `refuted` findings are only reported. The
entry rules decide how to fix — by default the main session fixes and runs the checks itself; the
environment's commit rules decide whether to commit; a re-review is added, with its one-line
reason, only when a fix could spread beyond where it was made. A finding that is a case stopping
the person (an exposed secret, a fix needing an irreversible operation) goes to the person
unfixed. Fix nothing when the person said to only look, when the target is not your own working
branch (someone else's branch, the merge target), or when the target is a document the person
approves (principles, glossary, specification) — only brainstorm changes those, so the report adds
guidance to call it. Handing over the report and asking "shall I fix these?" is a counter-example.
