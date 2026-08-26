# Review situation

Review is requested once for a branch, once for two commits, and once for an implementation run.
In another iteration a specification wording change keeps the same consequential decisions; later,
a persistence decision changes.

The first run explicitly selects `light`, the skill profile, a full model id, and one second
reviewer/model. Its safety result is incomplete once, then is retried with a bounded successful
result. The requested first model differs from the actual model used for the successful stage, and
the stage evidence must preserve both facts. An unknown profile and a second model without its
runner are also attempted and must be rejected. The second runner is unavailable; record a warning and continue without carrying that
permission into the next review.
