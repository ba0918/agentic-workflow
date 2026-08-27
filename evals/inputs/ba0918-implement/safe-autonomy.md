# Situation

The approved plan expects `src/validator.py`. A behavior test in `tests/validator_test.py` is
necessary but was omitted from Scope. The specification wording changed after approval without
changing behavior or architecture. Its committed `Verification coverage` maps the requirement to
`Step 1:test` and the guide requirement to `Step 2:artifact`; the caller offers a conflicting
`Step 1:check` override. An artifact step produced `docs/guide.md`.
