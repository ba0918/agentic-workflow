# Execution

Select the explicitly named plan, the just-approved plan, or the only file under `docs/plans/`,
in that order. Ask only when none or several remain. Require the plan to be committed and unchanged
from its approval commit.

Create or resume `.agents/evidence/<plan-key>/<run-id>/`, branch
`implement/<run-id>`, and one linked worktree. Never copy dirty main-checkout files into it.
When exactly one unfinished run exists and consequential decisions or dangerous targets did not
change, append `resumed` and continue automatically. Several candidates require a human choice.

At each step compare the approval commit's plan and specifications with current committed
documents. Return both versions and changed paths to the agent for semantic judgment. Record and
follow the current commit with `follow-documents` when no consequential decision changed; this
appends `recovering` with the changed documents, existing Git commit, and reason. Ask between
rebound and a new run only when one did. A rebound supplies the new approval commit, complete new
step contracts, and a one-to-one `old=new` mapping. Carry only completed steps whose completion
kind is unchanged, and resume at the first changed or new step.

Do not discard uncommitted work, unexplained commits, branches, worktrees, or evidence. Investigate
their meaning and carry safe ordinary work with an explicit terminal note.
