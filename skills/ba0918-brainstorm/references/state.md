# State and recovery

## Stored meaning

Store human-readable progress at `.agents/artifacts/ideas/progress/{session-id}.md` with:

- stable session ID, revision, and content identity;
- agreements, prohibitions, undecided and delegated matters, rejected options with reasons, and revisions;
- current position, next topic, and revision history.

Do not use one `current-session.md` as canonical state. Do not auto-convert legacy idea memos.

## Save and conflict

Use `scripts/state.py` to save atomically under the project-specific session path. Recheck the expected revision immediately before saving. On mismatch, preserve the current file and the candidate in a conflict file, report the conflict, and stop. Never overwrite or auto-merge. Do not rewrite bytes when meaning is unchanged.

Reject absolute paths, traversal, symlinks, secret-like content, duplicate IDs, unknown state kinds, broken revision references or history, and content-identity mismatches. Do not store credentials, personal data, or internal hostnames.

## Restore and lifetime

After compaction or interruption, validate progress before restoring the full semantic state and next topic. On validation failure, identify the damaged item and stop instead of guessing.

Remove progress only after the human approves wrap and the canonical write succeeds. Preserve it after rejection, incomplete readiness, or write failure.
