# State and recovery

## Stored meaning

Store human-readable progress at `.agents/artifacts/ideas/progress/{session-id}.md` with:

- stable session ID, revision, and content identity;
- agreements, prohibitions, undecided and delegated matters, rejected options with reasons, and revisions;
- current position, next topic, and revision history.

Do not use one `current-session.md` as canonical state. Do not auto-convert legacy idea memos.

## Save and conflict

Use `scripts/state.py` to save atomically under the project-specific session path. Recheck the expected revision immediately before saving. On mismatch, preserve the current file and the candidate in a conflict file, report the conflict, and stop. Never overwrite or auto-merge. Do not rewrite bytes when meaning is unchanged.

The helper owns only its fixed project-local `.agents/artifacts/ideas/progress/` layout. If `.agents/artifacts.yml` declares a different artifact policy, or `docs/ideas/` coexists as a legacy store, stop before creating directories and have the canonical local store resolved explicitly. Do not guess across stores or create split-brain state.

Reject absolute paths, traversal, symlinks, secret-like content, duplicate IDs, unknown state kinds, broken revision references or history, and content-identity mismatches. Before calling the helper, review the candidate state for credentials, personal data, internal hostnames, and information whose audience does not include the repository's maintainers. The helper's secret pattern is only a deterministic backstop, not authorization to persist other sensitive material.

## Restore and lifetime

After compaction or interruption, validate progress before restoring the full semantic state and next topic. On validation failure, identify the damaged item and stop instead of guessing.

If the required human is unavailable, keep the session incomplete and resumable; do not infer approval or write canonical content. Remove progress only after the human approves wrap and the canonical write succeeds. Preserve it after rejection, incomplete readiness, or write failure.
