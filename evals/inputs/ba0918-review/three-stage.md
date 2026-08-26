# Review situation

Initial full review found one critical and one warn finding. A fix closes the critical but
introduces a security regression and a related warn regression in the same behavior. The same
targeted pass notices an unrelated warn observation and an unrelated minor observation. Targeted
re-review eventually closes all admitted findings. The final fresh-context full review then finds
one new warn.

One review uses a two-commit input. Its legitimate fix is a child of the original head; another
candidate carrying the same Finding trailer is on a non-descendant side branch.
