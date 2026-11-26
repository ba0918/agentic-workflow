# Merging

Read only when the project's instructions say cycle goes on to merge and the person did not say
"no merge this time" for this run. The setting is the person asking for the merge in advance, so
once every condition below holds, go on without asking; asking "shall I merge?" then is a
counter-example.

## The four conditions

Have the branch merged only when all four hold:

1. **Look here first** in the terminal report is "none".
2. No success condition is unverified: the run ended converged, not with unverified remaining.
3. The checks pass (see **Checks**).
4. The change touches no path a person must see (see below).

Judge 1 and 2 over everything left in the branch's findings file, and 4 over the whole diff the
pull request merges (against the merge target), never against cycle's or iterate's comparison
base: a new iterate start on the same branch resets that base and would drop earlier changes from
the judgment. Condition 4 covers paths and what cycle reads in the diff; when in doubt, it is
touched. Add no agent to judge any of them.

When any is missing, leave the pull request and end with the terminal report, naming which
conditions are missing. Unverified remaining misses condition 2, so it opens the pull request and
stops there. Merging with a condition missing, or leaving something off **look here first** so the
merge can go ahead, is a counter-example.

## Paths a person must see

A change touching any of these is never merged, whatever else holds:

- a publishing, distribution, or version declaration (a package manifest's version, publish
  settings, a release workflow, a tag);
- credentials or secrets;
- reaching outside (network, external APIs, deploy, database migration);
- a deletion whose users cannot be enumerated;
- a CI workflow file — rewriting the checks would void condition 3;
- the project's instruction files (`AGENTS.md`, `CLAUDE.md` and the like) — they hold the merge
  setting and name the checks;
- the definitions of the checks the instructions name (check scripts, hook configuration) — for
  the same reason as a CI workflow file.

The project's instructions may add paths to this list, never remove any.

## Checks

In this order:

1. The hosting service's checks on the pull request (CI), when there are any: the service waits for
   them.
2. Otherwise the checks the merge target's copy of the project's instructions names, run here
   before opening the pull request.
3. Neither: do not merge. A review never stands in for a missing check.

Editing a check to make it pass is a counter-example.

## How

Push the branch and open a pull request whose body is the terminal report, against the
repository's default branch. When conditions 1, 2, and 4 hold, set it to be merged by the hosting
service once its checks pass (auto-merge); with local checks only, run them first and then open
it. The merge method is the repository's setting. Never merge locally into the target and push:
that bypasses branch protection and the hosting service's checks.

Once the merge is confirmed, say so in the terminal report and end. When the hosting service did
not merge (a failed check, for example), write why. The worktree and the local branch stay; the
main session cleans them up.

## Iterate

The same setting and conditions apply to ba0918-iterate, with condition 2 read through its
convergence reading. An iterate run that stopped at the judgment or ended on a hand-back never
merges.
