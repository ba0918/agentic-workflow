# State and recovery

Use `scripts/state.py` to store progress at
`.agents/tmp/ideas/<session-id>.md`. Keep the integer revision only to detect an old concurrent
writer. Do not store a document identity.

On revision conflict, preserve the current file and write the later candidate to a timestamped
conflict file. Revision comparison and replacement run under one exclusive lock so parallel
writers cannot both win. Stop for the human to choose; never overwrite or auto-merge. Validate
each item's shape, unique item IDs, allowed kind, required reason, and every revision reference.
Reject traversal, symlinks, malformed state, and sensitive content.

Restore agreements, prohibitions, unresolved and delegated matters, rejected options, revisions,
the current position, and the next topic from the file rather than guessing from conversation
memory. Remove it only after approved canonical documents were committed successfully.
