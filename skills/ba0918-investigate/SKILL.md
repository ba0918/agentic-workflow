---
name: ba0918-investigate
description: "Read-only investigation, called by a person and outside the ba0918 workflow stations: start from a symptom or a question, trace the direct and root cause, the impact, and whether tests cover it, then report fix options without changing a file. Use when asked to investigate something, to find why something happens, to look for a root cause, or to see the impact scope of a change. Not for checking a finished change — that is review's diagnosis. 日本語キーワード: 調べて 原因を調査して なぜ〜が起きる 影響範囲を見たい"
---

# Investigate

Take a symptom or a question a person states, find the cause and the impact by reading only, report, and
propose the next action. Never fix. Four things are investigated: confirm the problem, find the cause
(direct and root), analyse the impact, check the tests. Match the scope to the question: the whole
repository for a one-module question is too wide; one directory for one spanning three is too narrow.

This is an *investigation*: it starts from a symptom or a question, and its result has no
finding shape (no severity, no action, no oracle). A *diagnosis* is review called directly by a
person, starting from a target such as a diff or a document set. A person calls this skill on
its own; cycle never calls it — inside cycle, finding problems is review's job.

## Read-only guarantee

Do not edit, create, overwrite, delete, move, or rename any file, notebooks included. Leave the
repository and the file system as they were. The one exception: when the person explicitly
names a destination and asks for the report as a file, write it there. Asked for a file with
no destination, ask for one instead of choosing.

Allowed: reading files; listing paths; searching for strings or symbols; running commands known
to be read-only; following code references; delegating wide exploration to subagents. Tests may
run only when known not to update repository state (snapshots, caches, generated files) and to
have no external side effect (network writes, sent mail, external store updates); `git status`
cannot detect an external side effect, so do not run a doubtful test. Forbidden, as examples —
refuse anything else that could change state the same way:

- `rm` `rmdir` `mv` `cp` `chmod` `chown` `touch` `mkdir` `tee`
- output redirection and in-place rewriting
- state-changing git operations such as `commit` `push` `reset` `checkout --`

These instructions carry the guarantee, not a separate-context agent with a restricted tool set.
Take `git status` before and after the investigation; success means the two outputs are identical
apart from the requested destination. Writes to untracked places (caches, `.agents/`, temporary
directories) are forbidden too but invisible to `git status`; running only commands known to be
read-only and skipping doubtful ones covers them, and outside git, with no comparison, that alone
satisfies the guarantee. If the comparison, or the output of a command, shows a difference anywhere
but the requested destination, the guarantee is broken — see "When something goes wrong".

Secrets found along the way (credentials, tokens, keys): report that they exist, never their
value, and never copy them into a subagent prompt. One character of a key in the report is a
counter-example.

## Procedure

### Grasp the context

Take the problem as stated; look at the project's instruction files and the structure of the
directories involved; collect the errors, logs, stack traces, changed files, and specification
text that are available.

### Investigate the four

Within the scope the question calls for:

1. **Confirm the problem**: make the observed behaviour and the conditions it occurs under
   concrete.
2. **Find the cause**: follow the evidence to the direct cause (the place in the code) and,
   where it applies, on to a root cause at the design level.
3. **Analyse the impact**: affected callers, dependants, and other occurrences of the same
   pattern.
4. **Check the tests**: whether existing tests let the problem through. With no relevant test,
   write `no tests` in the impact section.

Do not stop at "probably here": the direct cause names the observed file and, where it applies,
the line.

### Delegate exploration

Delegate to separate-context subagents when any of these holds: the investigation spans three
or more directories; three or more angles should be explored in parallel; one angle needs a
cross-cutting search over five or more files. When none holds, read yourself. Even when one
holds, you may read yourself if the target is tightly bounded: a document investigation where
one search expression enumerates the core files, or a target within ten known paths. Put into every
subagent prompt, verbatim, the five parts of "Read-only guarantee" that bind the subagent: the ban on
editing, creating, overwriting, deleting, moving, and renaming; the allowed operations minus
"delegating to subagents" (a subagent never delegates further); running only commands known to be
read-only; the forbidden operations, and that they are examples; and the secrets rule. The report-file
exception and the `git status` comparison are the caller's: leave them out and state instead that the
subagent writes no file at all. Launch several subagents at once. A failed subagent is not retried;
read that part yourself. A subagent that changes state breaks your guarantee.

## Report

Return the report in the conversation, not in a file, unless the person explicitly named a
destination: the only reader is the person in front of you, and no later step reads it by
machine. Six sections, headings fixed in English, body in the language of the conversation:

```text
══════════════════════════════════════
INVESTIGATION REPORT
══════════════════════════════════════

## 1. Problem overview
## 2. Cause analysis
## 3. Impact
## 4. Confidence
## 5. Fix options
## 6. Recommended action
```

1: what is happening. 2: why — direct cause and, where applicable, root cause, kept apart. 3: affected
files, features, other occurrences of the pattern; `no tests` if none. 4: confidence, with two to four
items of evidence. 5: fix options. 6: recommended next action. A report missing a section is incomplete.

### Confidence

- **high**: checked mechanically against file contents, searches, or command output; any
  plausible counter-example lies outside the stated scope.
- **medium**: supported by reasoning, but a counter-example or an out-of-scope uncertainty remains.
- **low**: rests on limited evidence; more information or investigation is needed.

State uncertainty honestly; `high` on the strength of a file you did not read is a counter-example.

### Fix options

Sort each defect by whether it causes the stated symptom or the breakage the question points at.
One that does is a problem: give one to three options, each with where to change (file and place), a
summary, and pros and cons; another occurrence of the same pattern is a problem when it breaks the
same way; `keep as-is` is one option when leaving a problem alone is defensible. One that does not is
a future improvement. With no problem, begin section 5 with `no fix needed`. Whether or not options
exist, one or two future improvements may close section 5, outside the option format and never in
section 6. Only propose, never start a fix: "I fixed it" in section 5 is outside this responsibility.

### Recommended action

Pick one main recommendation; when several apply, list alternatives from lightest to heaviest.
Show invocations in a form that can be used as is.

| Situation | Recommendation | Ready-to-use form |
|---|---|---|
| Small task | iterate | `/ba0918-iterate <request>`; the request names the place and the change |
| No specification, no basis for a decision, or two readings | brainstorm | `/ba0918-brainstorm <topic>` |
| Specification exists, medium or larger change | plan, then cycle | `/ba0918-plan <specification path>` |
| Deferred | the person notes it down | one line to note |
| No fix needed | say so | `no further action needed` |
| Not enough evidence | keep investigating | the scope to investigate next |

A small task is one the ba0918-iterate skill accepts: the request has one reading, needs no
specification decision, contradicts no existing specification, and its impact is readable (every
file to change, files to be created included, can be enumerated in a closed list — no "there may be
others" — and what changes in each can be said without judgment); file count does not matter. A
change whose impact cannot be read, or which needs a specification decision, is medium or larger,
and sending it to iterate as "small" is a counter-example. There is no issue management here, so
"deferred" is the person's own note.

## When something goes wrong

When a difference shows up anywhere but the requested destination (for example, a test you ran
rewrote a snapshot), continuing would spread damage: stop. Show the person the `git status`
difference, or the output that revealed the change, and ask for a decision. Do not revert
yourself — reverting is an edit and breaks the guarantee a second time. Do not produce the
report; returning the six sections with a rewritten snapshot in place is a counter-example.

## Boundary with diagnosis

Checking a finished change against what was expected is diagnosis — review called directly by a
person — and not this skill's job. When that is what was asked, say so and stop without producing
the six-section report.
