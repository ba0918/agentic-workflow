# State and recovery

Use `scripts/state.py` to store progress at
`.agents/tmp/ideas/<session-id>.md`. Keep the integer revision only to detect an old concurrent
writer. Do not store a document identity.

Run the helper from the skill directory and resolve the target repository without embedding its
absolute path. Validate a state document before using it:

```sh
python3 scripts/state.py validate <<'JSON'
{"session_id":"session-1","revision":1,"current_position":"here","next_topic":"next","items":[]}
JSON
```

Save, load, and remove that state with the same JSON contract:

```sh
repo_root="$(git rev-parse --show-toplevel)"
python3 scripts/state.py save --repo "$repo_root" --expected-revision 0 <<'JSON'
{"session_id":"session-1","revision":1,"current_position":"here","next_topic":"next","items":[]}
JSON
python3 scripts/state.py load --repo "$repo_root" --session-id session-1
python3 scripts/state.py finish --repo "$repo_root" --session-id session-1 --approved --write-succeeded
```

The last command is only for the approved, successfully committed wrap boundary. Each successful
command writes one JSON object to standard output. Validation and save read one JSON object from
standard input.

On revision conflict, preserve the current file and write the later candidate to a timestamped
conflict file. Revision comparison and replacement run under one exclusive lock so parallel
writers cannot both win. Stop for the human to choose; never overwrite or auto-merge. Validate
each item's shape, unique item IDs, allowed kind, required reason, and every revision reference.
Reject traversal, symlinks, and malformed state.

Restore agreements, prohibitions, unresolved and delegated matters, rejected options, revisions,
the current position, and the next topic from the file rather than guessing from conversation
memory. Remove it only after approved canonical documents were committed successfully.
