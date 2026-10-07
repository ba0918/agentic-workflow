# agentic-workflow

[日本語](README-ja.md)

Development workflow skills for AI coding agents, packaged as
[Agent Skills](https://agentskills.io).

Five skills form one workflow. The agent interviews the person until both agree on a
specification, turns the specification into a plan that an implementer with no prior context
can execute, and then repeats implementation, adversarial review and fixing until the
findings converge. The person receives the result once, at the end.

Three more skills sit beside the workflow:

- one for a task too small to need a specification or a plan
- one for a read-only investigation
- one that decides which skill a new request starts from

Each skill passes the next one the path of the file it wrote. Nothing else connects them.
There is no runtime, no state store and no script.

## Skills

| Skill | Role |
|---|---|
| `ba0918-brainstorm` | Asks the person numbered rounds of questions, each with a recommended answer, until both sides understand the request the same way. Then writes the specification |
| `ba0918-plan` | Turns an approved specification into one Markdown plan. The plan links to sections of the specification instead of copying them, and gives each step its completion evidence and stop conditions |
| `ba0918-cycle` | A small orchestrator. Takes a plan and a branch, hands implementation, review and fixing to agents with separate contexts, and repeats until the findings converge |
| `ba0918-implement` | Executes a plan step by step. Writes tests first for code and makes one commit per concern. When the plan leaves a decision open, it picks a provisional answer and reports what would overturn it |
| `ba0918-review` | Reviews a diff or a set of documents adversarially. The reviewers run in separate contexts, return findings and never edit. A person can also call it directly to diagnose a codebase |
| `ba0918-iterate` | Entry point for a small task. Checks that the request is small, then runs cycle's loop on the request without a plan |
| `ba0918-investigate` | Investigates a symptom or a question without changing any file, and reports the direct cause, the root cause, the impact and the fix options |
| `ba0918-using-workflow` | Decides which skill a new request starts from: a small task, a medium or larger change with or without a specification, an unexplained defect, or a question that needs reading files. Answers questions and chat directly instead of routing them |

The skill bodies are in English and written for the agent. The specifications behind them,
the principles above the specifications and the glossary are in Japanese, in `docs/` and
`CONTEXT.md`. When two of these disagree, the principles override the specifications, and
the specifications override the skill bodies.

## Install

There are three kinds of route: a plugin, a package manager and a copy. Every route
installs the same skills. The routes differ in how you receive updates.

### Claude Code (plugin marketplace)

An installed copy follows the version in the marketplace entry, so you get an update when
that version goes up.

```
/plugin marketplace add ba0918/agentic-workflow
/plugin install ba0918-workflow@agentic-workflow
```

### Codex CLI (plugin marketplace)

Codex reads the same marketplace entry. The skills appear under the plugin name, for
example `ba0918-workflow:ba0918-brainstorm`.

```
codex plugin marketplace add ba0918/agentic-workflow
codex plugin add ba0918-workflow@agentic-workflow
```

### OpenCode (plugin)

Add the repository to `plugin` in `opencode.json`, either the project's file or the global
`~/.config/opencode/opencode.json`. Then restart OpenCode.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["agentic-workflow@git+https://github.com/ba0918/agentic-workflow.git"]
}
```

`.opencode/plugins/agentic-workflow.js` registers `skills/` as a skill path and does
nothing else. This route reads `package.json`, which describes the distribution and is not
a published package. `private: true` keeps it off the npm registry.

### APM (package manager)

[APM](https://github.com/microsoft/apm) manages skills for several agents from one
manifest. `apm install` adds the dependency to `apm.yml`, `apm.lock.yaml` records the
resolved commit, and `apm update` moves that commit forward.

```
apm install ba0918/agentic-workflow --target claude
apm install -g ba0918/agentic-workflow
```

APM warns about a dependency without a pin. Pin a release tag
(`ba0918/agentic-workflow#v{version}`) or a commit SHA.

### Copy (`gh skill` / `npx skills`)

These commands copy the skills into the project, and running them again pulls updates.
Naming one skill installs only that skill, and naming the repository installs all of them.
The five workflow skills call each other by name, so install them together.

```
gh skill install ba0918/agentic-workflow --agent claude-code --all
npx skills add ba0918/agentic-workflow
```

A copy contains only the contents of `skills/`. The specifications and the regression
scenarios stay in this repository.

## Keeping the entry skill resident

`ba0918-using-workflow` routes every new request, so the agent has to read it on every
turn, not only when its description matches. Add a pointer line to the project's agent
instructions (`AGENTS.md`, or the file your agent reads):

```markdown
## Important

- Always read `ba0918-using-workflow` first, before acting on a request
```

If the agent does not follow the pointer line, paste the skill body into those
instructions instead. You then have to update the pasted copy by hand.

## Optional review seats

A full review by `ba0918-review`, inside `ba0918-cycle` or called directly, can add
reviewers that run on other models. These optional seats get the same prompt as the
quality reviewer. Another model can catch findings the first one misses, and each seat
costs as much as one full review.

You list the seats in your user-scope instructions (for Claude Code, `~/.claude/CLAUDE.md`).
They live there because the models you can use depend on your own accounts, not on a
repository. Without a list, a review has no optional seats and runs as before.

Each entry gives:

- a name, which the report uses to say which seats took part
- a launch command or a skill to call. It takes the reviewer prompt and returns the
  findings as JSON
- an optional time limit. Without one, the review waits until the seat finishes

```markdown
## ba0918-review optional seats

- gpt: command `<your-cli> run -` (prompt on standard input). Time limit 15 minutes
```

Each seat runs in a throwaway copy of the worktree, and the copy is deleted when the seat
ends. The copy holds HEAD, uncommitted changes and untracked files, without untracked
symbolic links. Nothing a seat writes reaches your worktree. Running the seat's command
inside your own sandbox is still your job.

When a seat fails (quota exhausted, time limit, launch failure or unreadable output), the
review drops it without retrying and continues with the remaining reviewers. Diff reviews
use no optional seats.

To use fewer seats for one run, say so when you start it, for example "one seat this time"
or "only gpt". The count includes the quality reviewer, and a bare count takes seats from
the top of the list.

## Development

### Checks

```
bun install
bun run lint:docs                                  # textlint over docs/
bunx skills-ref validate skills/<name>             # the Agent Skills specification
```

CI runs the same checks on every push and pull request. It also checks that
`.claude-plugin/marketplace.json` and `package.json` declare the same version as
`.claude-plugin/plugin.json`.

### Releases

`.claude-plugin/plugin.json` holds the version. A release is one commit on `main` that
renames the `Unreleased` section of [CHANGELOG.md](CHANGELOG.md) to a heading with that
version. The release workflow then runs the checks, tags the commit and publishes a GitHub
release with that section as its notes. CHANGELOG.md marks a change to what a skill
instructs as breaking.

## License

MIT. See `LICENSE`.
