# Plan readability

Write normative prose in the human's language. The reader must understand what changes, why this
approach and order were chosen, what does not change, external effects, risks, human boundaries,
and how each step proves completion.

Do not copy specification behavior into the plan. Use `Verification coverage` to map every relevant
specification path and heading to the Step and completion kind that prove it. Explain
project-specific terms before relying on them. Keep uncertainty visible and never introduce a
requirement that first appears in the plan.

Before staging, verify every specification reference has a counterexample-sensitive direct proof,
supporting checks are not presented as proof, every Step has one completion kind and stop
condition, expected and explicitly excluded changes are visible, and the plan contains no manual
id, revision, document hash, or duplicate approval mechanism.
