# Execution

Select the explicitly named plan, the just-approved plan, or the only file under `docs/plans/`,
in that order. Ask only when none or several remain. Require the plan to be committed and unchanged
from its approval commit.

Create or resume `.agents/evidence/<plan-key>/<run-id>/`, branch
`implement/<run-id>`, and one linked worktree. Never copy dirty main-checkout files into it.
Before creating a run, discover every unfinished run that has not been logically retired. Show the
plan, run id, runtime-recorded start time (or explicit unavailable status for older version 2
bindings), last event, completed and remaining steps, and Git-derived branch, worktree,
unexplained-commit, and uncommitted-path facts. Do this even for one candidate and append nothing
until the human chooses. Resume only an explicitly selected run; derive all Git facts inside the
runtime rather than accepting caller claims.

When the human chooses a new run, append `resume-candidate-retired` with the reason to each old run
being set aside. Logical retirement removes it from default discovery but preserves evidence,
branch, and worktree, and an explicit run id can inspect or resume it later. Never retire by age or
inference and never expose physical deletion through this entry point. Do not repeat this startup
choice between synchronous delegates in the same cycle.

At each step compare the approval commit's plan and specifications with current committed
documents. Return both versions and changed paths to the agent for semantic judgment. Record and
follow the current commit with `follow-documents` when no consequential decision changed; this
appends `recovering` with the changed documents, existing Git commit, and reason. Ask between
rebound and a new run only when one did. A rebound supplies the new approval commit, complete new
plan, and a one-to-one `old=new` mapping; the runtime re-derives the complete new Step contracts
from that commit rather than accepting them from the caller. Map only Steps whose implementation
content is unchanged. Carry a mapped completion only when the completion kind and complete Human
gate contract are also identical; a change to the Step content, completion kind, or any Human gate
field resumes that Step. Resume at the first changed or new Step.

When the active Step declares a Human gate, return control to the human before crossing its
declared timing boundary. After the answer, record it with the complete dedicated command and then
resume the same Step:

```sh
python3 scripts/implement_runtime.py human-gate \
  --repo <repository> --plan-key <plan-key> --run-id <run-id> \
  --step <step> --gate-id <gate-id> --result <approved-or-rejected>
```

Use only the declared gate id and one of the declared results. The runtime resolves the gate target
and timing from the binding, rejects an answer outside that boundary, and keeps a rejected answer
distinct from approval.

Do not discard uncommitted work, unexplained commits, branches, worktrees, or evidence. Investigate
their meaning and carry safe ordinary work with an explicit terminal note.
