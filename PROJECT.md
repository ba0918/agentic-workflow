# Project Context

## What this is

One paragraph: what the project does and who uses it. Not a feature list.

## Stack and layout

The languages, frameworks and services in use, and where the significant directories are.

## Commands

| Purpose | Command |
|---|---|
| Install | `bun install` |
| Build | |
| Test | `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'` |
| Lint | `bunx agentic-skill-vendor verify`（正本と各 skill の複製の一致検査） |
| Run locally | |

## Conventions specific to this project

- Write LLM-facing instructions in English. This includes `AGENTS.md`, `PROJECT.md`, `SKILL.md`,
  and internal files under a skill's `references/` directory.
- Write human-facing artifacts in Japanese. This includes specifications, plans, roadmaps,
  decisions, reviews, and guides. Stable IDs, schema fields, code identifiers, and quoted external
  interfaces may remain in English.

## Constraints

Compatibility requirements, performance budgets, regulatory limits, and anything that makes an
obvious approach wrong here.

## Glossary

Domain terms whose meaning in this project differs from ordinary usage.
