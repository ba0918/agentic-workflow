# The review procedure

Every durable action goes through `scripts/review_runtime.py`; resolve its absolute path from
this skill directory. Each command takes `--repo <main-checkout> --plan-id <plan-id>
--attempt-id <execution-id>`.

## Verify the hand-off and bind

The input is one implementation execution whose evidence ends in `implementation_green`.
Never pick it from conversation memory: the helper reads the evidence directory and refuses,
before anything is written, when the last event is not the terminal completion, when the plan
or a specification no longer matches the fingerprint the implementation was bound to, or when
the worktree is missing or on another branch.

```text
python3 <review-runtime> bind --repo <main-checkout> --plan-id <id> --attempt-id <id> \
  --model <full-model-id> --model-source <explicit|project|user|session> [--continue]
```

An unfinished review of the same execution is shown, and only the human decides to continue
it (`--continue`); two reviews of one execution never run at once.

## Decide the model

Review depth follows the reviewing model's capability, and reviewing with the orchestrating
conversation's own model repeats its blind spots — prefer a stronger model. The choice is
never forced, but who reviewed is always recorded. Decide in this order and record which
stage decided:

1. an explicit `--model` at invocation;
2. the project's instructions (a reviewing model named in the project's agent rules);
3. the user's standing rules (for example a role-to-model table);
4. otherwise, the current conversation's model.

Model ids are full ids; aliases are refused because they drift across generations. When the
decided model differs from the current conversation, start a new conversation (a subagent) on
that model and have it perform the review there.

## First review

One reviewer runs the selected profiles once — never one AI per viewpoint, never re-reading
the input per viewpoint.

```text
python3 <review-runtime> inputs --level <light|standard> [--profile <name>] [--max-diff-lines <n>]
```

`inputs` lists the diff of the implementation branch and assigns each file group its profile;
`--profile` overrides. Adding or changing a profile never changes the skill body or its
scripts; profiles are prose without side effects and need no dedicated tests.

The human chooses the strength, and the command line always states it; `standard` is the
choice to reach for unless the human says otherwise. `light` collects only `security` and
`critical` candidates — a findings file carrying `warn` or `info` is refused as a whole.
Strength is never derived from diff size, because line counts do not measure impact; the
reviewer may suggest that `light` would do, but the human decides. Oracle-first, the
mandatory security check, and the re-review promises below do not change with strength.
Over the `--max-diff-lines` threshold the review stops and returns the split to the human:
splitting is a plan-granularity problem.

Read by severity candidate: for `security` and `critical` candidates, the diff plus the
direct callers of what the diff touched (one hop, inside the worktree, only after the
candidate exists) plus the affected specification sections; for `warn`, the diff alone; for
`info`, record only.

Write the oracle first for every finding; only a recorded reason why none can be written
makes it a human judgment — reluctance to write one is not a reason. A `warn` oracle may
rerun an existing test or a static check; writing new tests is not required. The mandatory
security items of the profile are part of the same review; report their completion in the
`security_check` field of the findings file.

Each finding in the findings file carries: `severity`, `action`, `spec_refs` (the
specification path and section it rests on), `evidence` (files, line ranges, a bounded
summary), `oracle` (or `oracle_unavailable_reason` for a human judgment), `root_cause_key`,
`state` (`open` when submitted), `spec_identities` (the specification fingerprints it was
judged against), and `profile` (which profile raised it). The id is derived; supply it only
to assert it matches.

```text
python3 <review-runtime> register --level <light|standard> --findings <findings.json> \
  [--profile <name>] [--profile-dir <dir>]
```

`register` validates every finding, runs each oracle, admits only those that fail now, and
freezes the set as one event with the model, strength, profiles, and reviewed paths. The set's
identity becomes the input every re-review round answers to, and the output groups the
admitted findings by root cause for presentation. Without a completed security check nothing
is frozen and the review stays resumable.

### Second reviewer

Only when explicitly asked (`--second-reviewer` with `--second-model`), once, alongside the
first review:

```text
python3 <review-runtime> second-opinion --second-reviewer <name> \
  --second-model <full-model-id> --command "<runner command>"
```

The package holds the plan text and the diff — never whole source files, never this review's
own findings. It is scanned for secrets before anything is sent; an unavailable runner
records a warning and the single-reviewer result stands. Read the output and pass its
problems to `register` as findings of the same set.

## Re-review after fixes

The fixing side reads the set and never rewrites its states. It names each finding's id in a
`Finding:` trailer of the fix commit; "I fixed it" is never an input. Problems the fixer
notices on the way go to a separate file as later candidates, not into the set. A
specification gap found while fixing goes back to the step that owns the specification, and
the review stops as `findings_stale`.

```text
python3 <review-runtime> reverify [--max-failures <n>]
```

`reverify` refuses a fix commit with no trailer and any id outside the set. It stops with
`findings_stale` when a specification the set relies on was revised — the human decides
whether to rebuild. Otherwise it runs each open finding's oracle: pass closes the finding,
failure keeps it open and counts. At `--max-failures` the finding is promoted to a human
judgment ("not fixed", not "no convergence"); without the argument nothing is promoted — the
counts accumulate and are reported, so pass the limit whenever the loop runs unattended. The
threshold is an operational value, which is why it arrives as an argument. A round-count cap
is never a termination condition. Fix commits that touch files outside the first review's
scope are recorded as a re-review candidate; a full re-review runs only when the human asks.
Human judgments are presented once per round, together:

```text
python3 <review-runtime> decide --finding <id> --result <accepted|rejected>
python3 <review-runtime> defer --findings <file.json> [--introduced]
```

`decide` closes one human-judgment finding with the recorded decision. `defer` records
problems noticed during re-review apart from the set; only with `--introduced` — a risk the
fix itself brought in — do findings join the set, under the same validation and
fails-now check as the first review.

A finishing review — one fresh full pass — runs only when the human asks for it on the spot,
once; its findings merge into the frozen set through the review-runtime `merge` command
(`merge --findings <file.json>`, the same fails-now admission as the first review) and close
through the same re-review loop.
