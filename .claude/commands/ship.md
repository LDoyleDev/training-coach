---
description: Verify and open a PR for the current branch
---
Ship the current branch:

1. `make check`. If anything fails, fix it and run again. Do not continue until it is green.
2. Review your own diff (`git diff main...HEAD`) against CLAUDE.md "Code rules" and
   "Security rules" and the threat model. Fix what you find.
3. Confirm: tests cover new behaviour; migration has a downgrade; `.env.example` and docs are
   updated; an ADR exists for any new decision.
4. Commit any remaining changes with a Conventional Commit message, push with
   `git push -u origin HEAD`.
5. `gh pr create` with a Conventional Commit title and the PR template filled in, including
   `Closes #<issue>` and how it was tested. Report the PR URL.

Never merge the PR yourself.
