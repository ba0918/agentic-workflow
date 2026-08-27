# Check, artifact, and external steps

A check step runs the exact commands named by the plan, in order. Every command must succeed.
Commit changed files after all-path safety checks; a check that changes nothing needs no commit.
Do not add, remove, reorder, or replace those commands at the caller boundary; change the approved
plan if its declared portfolio is consequentially wrong.

An artifact step records produced paths and format checks so an independent reviewer can judge its
meaning. An external step records what was checked and a bounded result summary. Neither asks for a
human verdict during implementation. Perform external work only when it is reversible and
authorized; human-only permission, external publication, production configuration or data, and
irreversible work return before execution.

Do not persist raw command or provider logs.
