# Record kinds

The progress file `.agents/tmp/brainstorm-<name>.md` holds the current state only: the
position in the tree, the next round, and the items below. Overwrite it when meaning changes;
do not append a log.

| Kind | Holds | Goes to |
|---|---|---|
| agreement | what was decided, in the person's words when possible | specification body |
| prohibition | what will not be built | the specification's "not built" section |
| undecided | the open question and **who decides it** (person, or a later brainstorm — never the implementer: that is delegated) | "Undecided" section |
| delegated | a choice the person agreed to leave to implementation, and **why** every option keeps approved behavior — never filed before they answer | "Delegated" section |
| rejected | the alternative and **why** it lost | "Rejected" section, one line each, no mechanism description |
| revision | what replaced what, and why | progress file only; git history carries it after approval |

Undecided has no answer yet. Delegated has an answerer chosen. Never file one as the other.

Recommended answers that the person did not answer are not agreements; keep them as undecided
until answered.

Minimal layout of the progress file:

```markdown
# <name>

Position: <where in the tree; what the next round covers>
Glossary updates pending: <terms and readings>

## Agreements
- A1 ...
## Prohibitions
- P1 ...
## Undecided
- U1 ... (decides: person)
## Delegated
- D1 ... (why: ...)
## Rejected
- R1 ... (why: ...)
## Revisions
- A3 replaces A1: ...
```
