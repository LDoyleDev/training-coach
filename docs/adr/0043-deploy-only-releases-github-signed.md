# ADR-0043: The Pi deploys only releases GitHub signed

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

The Pi deploys the newest release tag by itself (ADR-0030). It already refuses a tag that isn't
on `main`, one that moved, and anything over local changes. But being on `main` only shows
someone could write to it: a push past the pull requests (a leaked token with admin rights, an
override of branch protection) would deploy like any release. The security review asked the Pi
to check that a release is genuine before running it.

Every commit GitHub makes itself, squash merges of pull requests included, is signed with
GitHub's own key (`https://github.com/web-flow.gpg`). A commit pushed from anywhere else isn't.

## Decision

Before deploying, `scripts/auto-deploy.sh` checks the release's commit carries a good
signature by GitHub's key, and refuses it otherwise.

- The key is in the repo (`scripts/keys/github-web-flow.gpg`) and its fingerprint
  (`968479A1AFF927E37D1A566BB5690EEEBB952194`) is pinned in the script. Both are read from
  the checkout already deployed, so a new release can't change what vouches for it.
- The check uses a throwaway gpg home each run: nothing to set up on the Pi but `gnupg`
  (installed with Raspberry Pi OS). No gpg means no deploy.
- A refused release fails the unit, so it alerts on Telegram (#168).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| GitHub's merge signature (chosen) | Automatic; proves a merge on github.com, so the pull request and required checks; no setup | Trusts GitHub and the account: someone signed in as Liam can still merge |
| Liam signs each release tag with his own key | Proves Liam approved it, even if GitHub is compromised | A key to keep safe and a manual step per release; deferred until there's a hardware key |
| Ask GitHub's API whether the checks passed | Checks CI directly | Same trust in GitHub; a network call and its failure modes; branch protection already requires them |

## Consequences

- A commit on `main` that GitHub didn't make (a direct push) is never deployed automatically.
- When GitHub rotates its key (last in January 2024), deploys stop with an alert. Then update
  the key file and fingerprint in a PR, release, and deploy that release by hand (deploy
  runbook).
- It doesn't help if Liam's GitHub account is taken over: that is GitHub's own protection
  (passkey). Signing releases with a personal hardware key is the step after this one.
