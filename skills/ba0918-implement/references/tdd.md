# Test steps

Follow RED, GREEN, REFACTOR, commit in order.

1. Write one behavior test before product code and run it. Accept only a failure caused by the
   behavior being absent.
2. Freeze the test, fixtures and command bytes. This test snapshot is the workflow's only content
   hash because Git cannot prove that the passing test is the same test that failed.
3. Write the minimum product code, run the frozen test and the complete relevant suite, and record
   GREEN.
4. Refactor only when duplication, naming, or responsibility warrants it. Otherwise record what
   was examined and why no change was needed. Re-run the frozen test and suite after refactoring.
5. Apply all-path safety checks, commit one concern, and append the commit event.

If the frozen test must change, establish a new genuine RED before product work continues. Never
weaken a test to manufacture GREEN.
