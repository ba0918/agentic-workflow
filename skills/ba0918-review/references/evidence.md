# Review records

Review records live next to the implementation evidence they judge, under the same
one-event-one-file, append-only rules:

```text
.agents/artifacts/executions/<plan-id>/<execution-id>/review/
```

- Review keeps its own sequence and never writes into the implementation's event chain; the
  first event (`review-bound`) references the identity of the implementation's last event.
- The frozen findings set (the `findings-fixed` event) is never overwritten. Findings open and close by
  appended events only; after a refusal or a stop the set file stays.
- A refusal that leaves the review resumable is returned as a command error and writes no
  event; the terminal rows below are written only when the condition itself must be durable.
- One execution has at most one running review. An existing unfinished review directory is
  shown to the human, who decides whether to continue it. There is no repository-wide
  in-use marker.

| Event | Meaning |
|---|---|
| `review-bound` | the review started against a verified hand-off |
| `model-selected` | which model reviews, and which stage of the order decided it |
| `findings-fixed` | the frozen set: findings, their set identity, model, strength, profiles, reviewed paths |
| `review-incomplete` | the review stopped resumable (for example an unfinished security check) |
| `reverify` | one re-review round: the fix commits seen and each finding's verdict |
| `findings-added` | risks the fix introduced, admitted into the set |
| `decision` | a human decision closing a human-judgment finding |
| `deferred` | problems recorded apart from the set as later candidates |
| `findings_stale` | a specification the set relies on was revised; terminal, the human decides |
| `rereview-candidate` | fixes touched files outside the first review's scope |
| `warning` | a non-blocking degradation (for example an unavailable second reviewer) |
| `stopped` | a durable terminal stop on a blocking condition |

The second reviewer's input package and output are working files under
`.agents/tmp/reviews/<review-id>/`, not part of the durable record. `.agents/artifacts/reviews/`
is a place for human-facing reports; it is never the canonical record. Full command output,
external service logs, secrets, personal data, and internal host names are never copied into
any record.
