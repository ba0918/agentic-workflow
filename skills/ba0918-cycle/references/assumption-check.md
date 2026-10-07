# Assumption check

Read when one of the first four conditions of ending 3 holds. Fixes that keep failing to clear,
bring a closed cause back, fail to shrink the new findings, or raise new findings near themselves
usually share a wrong assumption; fixing again on the same assumption moves the problem without
removing it. Before ending on no progress, name that assumption and swap it once. Cycle does this
itself, as the loop's only judge; no agent or seat is added.

First read the findings file's `assumption_attempts`. An attempt carrying the current comparison
base means this run already tried: end with ending 3 without trying again.

1. **Write the assumption stack.** Read the commits of the fixes behind the condition, the findings
   each addressed, and the assumptions fixers reported for re-delegated findings. Write the
   assumptions those fixes shared, one sentence per level: the most specific one (where the last
   fix touched) at the bottom, and what the others rest on above it. Mark each level as living in
   the implementation, or in the plan or specification.
2. **Swap the top assumption.** Of the assumptions the findings put in doubt, take the topmost.
   Write what replaces it and which findings point there.
3. **Record the attempt** in `assumption_attempts` before delegating anything.
4. **Send or end.** If fixing on the replacement contradicts neither the approved specification nor
   the plan, give a fixer the visible findings, the stack, and the replacement, to fix from the new
   assumption instead of patching the last finding; the loop continues from the diff review after
   that fix. If it would contradict them, do not try: end with ending 4, and the terminal report
   carries the stack, the change proposed for the specification or plan, and guidance to call
   brainstorm or plan. Cycle edits neither.

**One try per run**; swapping again would only move the whack-a-mole to the assumption layer. A
run is one plan's cycle, resume and "run more" included, or one start of iterate; iterate resets
the base at each start, so a new start may try again. After the try, reset ending 3's streaks:
counted on, the condition would hold again right after the next review.

Counter-examples: deleting the record to try again; ending with ending 3 without this check when a
condition held; trying twice in one run; changing the approach from the last finding alone, with no
stack written.
