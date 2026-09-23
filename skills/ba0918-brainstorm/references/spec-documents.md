# Specification documents

Read this before writing a specification. A large specification contradicts itself and hides
it; people and models alike miss contradictions in a large context. So keep each specification
small and every fact in one place. This lowers the chance of a contradiction; it guarantees
nothing.

## One responsibility, one specification

A responsibility is what changes for the same reason — for a specification, a group of
requirements. Decide by it whether to add to an existing specification or start a new one: a
requirement that would change for a different reason than those already there gets a new
specification. One session may change several; together they are still one deliverable under
the conditions for handing to plan. The workflow does not decide directory layout or file
names; follow whatever layout the project uses. For example, a small project may keep its
specifications flat under the specification home, and a large one may split them by domain.

## One fact, one place

Before writing a new requirement, text-search the specification home the project's instructions
name for its central words. If the fact is already written, link to it instead of writing it
again; a copy drifts when only one side is fixed.

## References are links

Refer to another specification with a Markdown link, and to a heading with its anchor, such as
`[Finding fields](review.md#finding-fields)`. Never refer by section number, "above", or "as
stated earlier". This binds the references you write in this revision and those you re-point
when splitting; do not sweep existing documents for old non-link references. When you split a
specification, re-point every old reference the split leaves behind as a link, in the same
change. When you rename a heading or move a document, text-search for links to the old name and
fix them in the same change; no tool checks links for you.

## When to split

The guide for one specification is 300 lines, counted as the file's raw line count. The number
has no grounds yet; it is a placeholder. When a revision would take a specification past it,
check whether its responsibilities are mixed. If they are, carve out only the responsibility this
revision touches into its own specification and leave the rest as it is; if not, leave it whole.
Show your conclusion and what you carved out as a judgment point when asking for approval.
Cutting sentences to fit the number, or splitting where no responsibility boundary runs, is a
counter-example: promises that depend on each other, once split apart, hide their
contradictions. Never reorganize an already large specification wholesale; check it when a
revision reaches the guide.

## After a split

- **Index**: one per split specification. It holds only a link to each part with a one-line
  description, and no requirements. People start reading there and a revision of that scope
  starts there; plan does not start from it.
- **Rejected, undecided, and delegated** items go in the specification of the responsibility they
  concern, never collected into one document: a rule and the note delegating it must be seen
  together.
- **Glossary**: one by default (the repository's `CONTEXT.md`). Split it into a domain's
  directory only when the same term means different things across domains.
