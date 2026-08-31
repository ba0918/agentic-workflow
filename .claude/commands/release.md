---
description: Cut a release — promote the changelog, align the version declarations, run the checks, and push main so the release workflow tags it and publishes the GitHub release
---

Release this repository. The person has already decided to publish by invoking this command;
what remains is the version, the notes, and one push. Read the skills `ba0918-release` and
`ba0918-commit` before starting, and follow them.

## Preconditions — stop if any fails

- The current branch is `main`, the working tree is clean, and after `git fetch origin`,
  `main` equals `origin/main`.
- The `## [Unreleased]` section of `CHANGELOG.md` has at least one entry. An empty section
  means there is nothing to release; say so and stop.

## Steps

1. **Choose the version.** The canonical version is `.version` in
   `.claude-plugin/plugin.json`. Compare it with the newest published tag
   (`git ls-remote --tags origin`). If the canonical version has no tag yet, it is the
   candidate; otherwise derive the candidate from the unreleased entries: while the major is
   0, a **BREAKING** entry or an `Added` entry moves the minor, and `Fixed` alone moves the
   patch. State the version and the reason in one sentence when presenting the draft.

2. **Write the draft.** Set the version in `.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json` (`plugins[0].version`) and `package.json`. In
   `CHANGELOG.md`, insert `## [<version>] - <today, YYYY-MM-DD>` directly under an
   emptied `## [Unreleased]` so the entries move under the new heading unchanged, then
   rewrite the link definitions at the bottom: `[Unreleased]` compares `v<version>...HEAD`,
   and `[<version>]` compares `v<previous>...v<version>`, or points at
   `releases/tag/v<version>` for the first release. Touch nothing else.

3. **Run the checks** the release workflow will run, and stop without committing if any
   fails:

   ```
   bun run lint:docs
   for skill in skills/*/; do bunx skills-ref@0.1.5 validate "$skill"; done
   ```

   and the version agreement: the three declarations from step 2 must be identical.

4. **Get the draft approved.** Show the diff with the `diff-review-viewer` skill, naming the
   version, the date, and the notes as the approval target. On rejection, restore the
   working tree (`git checkout -- .`) and stop.

5. **Commit and push.** Stage exactly the four files from step 2 and commit as
   `chore: v<version> をリリースする` with a body saying what this release delivers to
   someone who installed the previous one. Then `git push origin main`. Do not create a
   tag: the release workflow tags the commit after the checks pass on it and publishes the
   GitHub release with the changelog section as its notes. A tag pushed from here would
   name a state nobody has verified.

6. **Report.** Give the run URL (`gh run list --workflow Release --limit 1`), what the
   workflow does next, and the command that confirms the result once it finishes
   (`gh release view v<version>`). If the workflow fails, nothing has been tagged: fix
   the cause on `main`, and run this command again — the promote commit is redone on top.
