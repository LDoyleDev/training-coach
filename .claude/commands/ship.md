---
description: Verify and open a PR for the current branch
---
Ship the current branch:

1. `make check`. If anything fails, fix it and run again. Do not continue until it is green.
2. Review your own diff (`git diff main...HEAD`) against CLAUDE.md (root and the nested
   `backend/` and `frontend/` files) and the threat model. Fix what you find.
3. Run the `security-reviewer` subagent on the branch. If the diff touches `backend/migrations/`
   or `backend/src/training_coach/db/`, also run the `migration-reviewer` subagent. Fix every
   **blocking** finding, then run `make check` again. Put advisory findings you chose not to fix
   in the PR description with a reason.
4. Confirm: tests cover new behaviour (a bug fix has a test that failed before it); migration
   has a downgrade; `.env.example`, API types and docs are updated; an ADR exists for any new
   decision; the diff is under ~400 changed lines excluding lockfiles, generated files and
   migrations, or the PR says why not.
5. Commit any remaining changes with a Conventional Commit message, push with
   `git push -u origin HEAD`.
6. `gh pr create` with a Conventional Commit title and the PR template filled in, including
   `Closes #<issue>`, how it was tested, and the reviewers' results. Report the PR URL.

Never merge the PR yourself.
