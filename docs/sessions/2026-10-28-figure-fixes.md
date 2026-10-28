# Session log: 28 Oct 2026 (1.7.1): the follow-up pass on figures that didn't read well

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-28-home-gym-levels-figures.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.7.0 (live on the Pi 28 Oct 13:27) | builder step 9, "Change level" in a session, the gym and step figures (see the previous log); the three migrations ran in order |
| 1.7.1 (released with this log) | #417 front views fill their picture, the chest fly front-only (its side view read as a front raise), the Pallof cable column beside the person with a front view, the reverse pec deck as a seated machine; #419 props stand out in dark mode (light unchanged); #420 Nordic curls hook under a sofa, reverse Nordics about twice as big; #422 the archer push-up seen from in front of the head; this log |

## Decisions and where they live

- **Figures** (Liam, 28 Oct: merge the gym figures and follow up the weak ones): ADR-0063.

## State at the wrap

- **Pi.** v1.7.0 live since 13:27 on 28 Oct; 1.7.1 deploys about 15 minutes after its release.
- **Worktrees** cleaned on 28 Oct; only the main checkout is left. Local branches whose remote is
  gone are kept.

## Open items and next steps

1. **Figures still off:** the reverse pec deck's levers cross the face in the front start view;
   the Nordic curl came out about 6% smaller, not bigger (its lying end pose and the sofa fill
   the width).
2. **Waiting on Liam:** approve reader 0.0.7 in the `android-release` environment; the backup
   key in the password manager, Cloudflare "Always Use HTTPS", the desktop's `User` account,
   BitLocker status.
3. **Next builder work** and **follow-ups:** unchanged from the previous log's list.
