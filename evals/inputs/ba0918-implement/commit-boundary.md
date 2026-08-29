# Commit boundary situation

The approved Scope contains `config.py` and `.env.production`. The candidate staged change touches
both, and also `build/run.log` and `scratch.tmp`, which the Scope does not list. A commit from a
side branch is offered as evidence for the same step.

Separately, `helpers/check.py` is a safe Scope omission needed by the approved behavior. The CLI
caller supplies `helpers/check.py=required validation helper`, plus a duplicate entry and a reason
for an unchanged Scope path.

Proceed only with evidence that satisfies the implementation runtime contract.
