---
description: Start work on a GitHub issue (branch, read spec, plan)
argument-hint: <issue-number>
---
Start work on issue #$ARGUMENTS.

1. `git switch main && git pull --ff-only`.
2. `gh issue view $ARGUMENTS` and read it fully, including the spec step it references in
   `docs/specs/`. Read any ADRs it touches.
3. Create the branch `<type>/$ARGUMENTS-<short-slug>` (type from the issue: feat, fix, docs, chore).
4. Write a short plan: files to change, tests to add, migration needed (yes/no), any decision
   that needs a new ADR. Show me the plan and wait for my OK before writing code, unless the
   issue is labelled `size: S`.
