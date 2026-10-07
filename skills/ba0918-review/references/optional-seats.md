# Optional seats

Read by the caller before a full review or a direct call, when the person's user-scope
instructions list optional seats.

- **The list.** Each entry in the person's list names the seat, its launch means (a command to
  run or a skill to call), and, optionally, a time limit. This skill names no seat, tool, or
  skill of its own.
- **How many.** The person's word for this run ("one seat this time", "all seats", "only gpt")
  or the caller's one-line reason overrides the count; otherwise run every seat on the list. The
  count includes the required quality reviewer and never the conformance reviewer: "one seat"
  means no optional seat. A word may name seats; a count without names takes optional seats in
  the order the list gives them.
- **Which reviews.** A review another station runs on its own, not through this skill, gets none.
- **Launching.** The caller launches optional seats itself; a reviewer delegation never carries the
  list or this file. Seats may be launched in parallel. Hand each launch means the
  self-contained prompt the quality reviewer gets, rewritten for the seat's copy (below): the
  copy's path wherever the worktree's path appears, and every file the prompt references placed
  inside the copy or inlined. Run the launch means with the copy as its working directory, and read
  what it returns as the JSON in **Output**.
- **Throwaway copy.** Each seat runs inside its own copy of the worktree, created in a temporary
  directory outside it right before that seat is launched: the worktree's HEAD with its
  uncommitted changes and its untracked, non-ignored files laid over it (for example, a
  `git clone --shared` of the repository checked out detached at HEAD with its remote removed,
  `git diff HEAD --binary` applied in it when not empty, and the untracked files copied in).
  Leave out untracked symbolic links: a copied link still points where it did, and a seat
  writing through it reaches the person's worktree. The copy has its own repository, so a seat's
  stash, branches, and config stay in it. The caller that created the copy deletes it when the
  seat ends, whatever the outcome (its JSON read, or the seat absent for any reason); the copy is
  not one of the person's worktrees. Nothing a seat writes reaches the person's worktree.
- **Time limit.** Apply one only when the seat's entry writes it; otherwise wait for the launch
  means to finish.
- **Absent seats.** An optional seat that fails once is absent and is never retried. The reasons:
  quota exhausted, time limit reached, launch failed, and output unreadable as finding JSON. An
  absent optional seat does not stop the review or make it unsuccessful. A required seat that
  fails is handled as a failed review already is.
- **Merging and reporting.** The caller merges and dedupes optional seats' findings with the others
  as **Output** says; the finding shape does not change, and several seats raising the same thing
  adds no weight. The report states which optional seats attended and which were absent, each
  absence with its reason.
