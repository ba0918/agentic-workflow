# agentic-workflow

Development workflow skills for AI coding agents, packaged as
[Agent Skills](https://agentskills.io).

Five skills form one workflow: interview the person until the specification is agreed,
turn it into a plan an implementer with no prior context can execute, then loop
implementation, adversarial review and fixing until the findings converge, handing the
result to the person once. Three more stand beside it, for eight in all: one for a task
too small to need a specification or a plan, one for a read-only investigation, and one
that decides which of the others a new request enters from. Each skill hands the next
one the path of what it produced, and nothing else ties them together — there is no
runtime, no state store and no script. This is a collection of skills, not a framework.

## Skills

| Skill | Role |
|---|---|
| `ba0918-brainstorm` | Interviews the person in numbered question rounds with recommended answers until shared understanding is complete, and writes the specification |
| `ba0918-plan` | Turns an approved specification into one Markdown plan, referencing specification sections instead of copying them, with completion evidence and stop conditions per step |
| `ba0918-cycle` | A small orchestrator: takes a plan and a branch, delegates implementation, review and fixing to separate-context agents, and loops until the findings converge |
| `ba0918-implement` | Executes a plan step by step, test-first for code, one commit per concern, and hands back instead of guessing when a design decision is missing |
| `ba0918-review` | Adversarial review of a diff or a document set by separate-context reviewers that return findings and never edit; also callable on its own for a diagnosis |
| `ba0918-iterate` | Entry point for a small task: a separate-context judge proposes whether the request is small, then cycle's loop runs on the request instead of a plan |
| `ba0918-investigate` | Read-only investigation from a symptom or a question to the direct cause, the root cause, the impact and the fix options, without changing a file |
| `ba0918-using-workflow` | Decides which skill a new request enters from — small task, medium-or-larger change with or without a specification, unexplained defect or question needing file reading — and answers questions and chat directly instead of routing them |

The skill bodies are in English, written for the agent. The specifications they were
written from, the principles above them and the glossary are in Japanese, under `docs/`
and `CONTEXT.md`; when they disagree, the principles win over the specifications, and the
specifications over the skill bodies.

## Install

Three kinds of route are supported — plugin, package manager and copy. They differ in how
updates reach you, not in what you get.

### Claude Code (plugin marketplace)

An installed copy follows the version declared in the marketplace entry, so an update
reaches you when the version is bumped.

```
/plugin marketplace add ba0918/agentic-workflow
/plugin install ba0918-workflow@agentic-workflow
```

### Codex CLI (plugin marketplace)

Codex reads the same marketplace entry, and the skills appear under the plugin name as
`ba0918-workflow:ba0918-brainstorm` and so on.

```
codex plugin marketplace add ba0918/agentic-workflow
codex plugin add ba0918-workflow@agentic-workflow
```

### OpenCode (plugin)

Add the repository to `plugin` in `opencode.json` — the project's or the global
`~/.config/opencode/opencode.json` — and restart OpenCode.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["agentic-workflow@git+https://github.com/ba0918/agentic-workflow.git"]
}
```

`.opencode/plugins/agentic-workflow.js` registers `skills/` as a skill path and does
nothing else. This route reads `package.json`, which is here as a distribution manifest
rather than a published package: `private: true` keeps it off the npm registry.

### APM (package manager)

[APM](https://github.com/microsoft/apm) manages skills for several agents from one
manifest. Installing adds a dependency to `apm.yml`; `apm.lock.yaml` pins the resolved
commit, and `apm update` moves it forward.

```
apm install ba0918/agentic-workflow --target claude
apm install -g ba0918/agentic-workflow
```

APM warns when a dependency is unpinned — pin a release tag
(`ba0918/agentic-workflow#v{version}`) or a commit SHA.

### Copy (`gh skill` / `npx skills`)

Skills are copied into the project at install time, and updates are pulled by running the
command again. Naming one skill installs that skill alone; naming the repository installs
all of them. Because the five workflow skills call each other by name, install them
together.

```
gh skill install ba0918/agentic-workflow --agent claude-code --all
npx skills add ba0918/agentic-workflow
```

What a copy route installs is the contents of `skills/` and nothing else — the
specifications and the regression scenarios live outside that directory.

## Keeping the entry skill resident

`ba0918-using-workflow` routes each new request, so it must be read every turn, not only
when its description fires. Add a pointer line to the project's agent instructions
(`AGENTS.md` or the equivalent your agent reads):

```markdown
## Important

- Always read `ba0918-using-workflow` first, before acting on a request
```

Where a pointer line turns out not to be followed, inlining the skill body itself into
those instructions is the reliable fallback, at the cost of updating it by hand.

## Optional review seats

A full review by `ba0918-review` (inside `ba0918-cycle`, or called directly) can add
reviewers run by other models — optional seats — alongside its quality reviewer, with the
same prompt. Different models miss different things; each seat costs a full review's worth.
The seats live in your user-scope instructions (for Claude Code, `~/.claude/CLAUDE.md`),
because which models you can use depends on your own accounts, not on a repository. With no
list there are no optional seats and reviews run as before.

Each entry gives:

- a name, used when the report says which seats attended
- a launch means: a command to run or a skill to call, which takes the reviewer prompt and
  returns the findings JSON
- optionally, a time limit; without one the review waits for the launch means to finish

```markdown
## ba0918-review optional seats

- gpt: command `<your-cli> run -` (prompt on standard input). Time limit 15 minutes
```

Each seat runs inside a throwaway copy of the worktree (HEAD plus uncommitted changes and
untracked files, untracked symbolic links left out), deleted when the seat ends, so
nothing a seat writes reaches your worktree. Wrapping the launch means in your own sandbox
is still up to you.

A seat that fails (quota exhausted, time limit, launch failure, unreadable output) is
absent and never retried; the review goes on with the rest. Diff reviews get no optional
seats. To use fewer seats for one run, say so when starting it — "one seat this time",
"only gpt"; the count includes the quality reviewer, and a bare count takes seats in list
order.

## Verification

```
bun install
bun run lint:docs                                  # textlint over docs/
bunx skills-ref@0.1.5 validate skills/<name>       # the Agent Skills specification
```

CI runs the same checks on every push and pull request, and additionally checks that
`.claude-plugin/marketplace.json` and `package.json` declare the version
`.claude-plugin/plugin.json` declares.

## Releases

The version is declared once, in `.claude-plugin/plugin.json`. A release is one commit
on `main` that promotes the `Unreleased` section of [CHANGELOG.md](CHANGELOG.md) to a
version heading matching it; the release workflow then runs the checks, tags that commit
and publishes a GitHub release whose notes are that section. Changes that alter what a
skill instructs are recorded there as breaking.

## License

MIT. See `LICENSE`.
