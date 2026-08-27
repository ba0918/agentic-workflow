# Situation

For one plan, first there is exactly one unfinished run with no consequential document change.
Do not resume it automatically: show its safe runtime/Git summary and ask whether to continue,
rebound, or logically retire it before starting new. Later a separate scenario has two unfinished
runs for that plan. One older version 2 binding has no recorded start time; report that as
unavailable rather than deriving it from filesystem timestamps.

The unique run uses version 2 evidence. Its plan wording changed without moving a consequential
decision, then an approved revision renames one equivalent completed check step and adds a new
external step. Preserve the equivalent step through an explicit one-to-one mapping.

If the human starts new, retain the old run's evidence, branch, and worktree while excluding it
from default discovery with a reason. An explicit run id must still permit investigation or resume.
