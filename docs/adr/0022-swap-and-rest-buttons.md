# ADR-0022: What Swap and Rest today do to the queue

- Status: Accepted
- Date: 2026-10-06
- Deciders: Liam

## Context

Step 1-D puts three buttons on the morning message: Start, Rest today and Swap. ADR-0016 said
a swap must be an explicit action but did not define it. Liam asked for Swap to offer three
choices: do the next session first, pick another session, or push today's to tomorrow.

"Do the next session first" cannot be expressed with the queue pointer alone. Doing the next
session out of order leaves the pointer in place (ADR-0016), so the next session would come
round again two days later.

## Decision

- **The queue gains a short list of queued sessions** (`plan_state.queued`). When the pointer
  moves it takes the first queued session; once the list is empty the cycle resumes. Without
  a swap the list is empty and nothing changes from ADR-0006 and ADR-0016.
- **Do the next one first**: with sessions P N A B ..., the order becomes N P A B ... (pointer
  N, queued P then A). Neither session comes round twice. Swapping again swaps within the
  queue. A plan with one session cannot swap.
- **Pick another session**: shows that session for today. The queue does not change; doing it
  is an out-of-order session (ADR-0016), so the offered session is still next.
- **Push to tomorrow**: logs a `skipped` workout for the offered session. The pointer stays,
  everything shifts a day (ADR-0006) and the evening nudge is silenced (ADR-0014).
- **Rest today**: on the optional rest session it logs `rest`, which counts as done and moves
  the queue (ADR-0006: a planned rest counts as done). On any other session it behaves like
  Push to tomorrow, so resting never drops a training session from the cycle.
- **Every button names the session it was offered for.** If the queue has moved on, the press
  changes nothing and the bot says the message is out of date. Each action is logged as an
  event (`queue.rest`, `queue.pushed`, `queue.swapped`, `queue.picked`).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Queued list on plan state (chosen) | Pure, testable rule; any number of swaps; one JSON column | A migration |
| Swap the two templates' positions | No new state | Changes the order of every future cycle |
| Skip sessions done out of order when the pointer moves | No new state | Needs history queries in the rule; surprising when a session is repeated on purpose |
| Rest today always advances | Simplest | A tired day would silently drop leg day from the cycle |

## Consequences

- `domain/queue.py` works on a `Position` (pointer plus queued sessions); `/week` shows swaps.
- A held session (Push to tomorrow, or Rest on a training session) can still be done the same
  day: logging it then counts as normal and moves the queue.
- Text logging (1-E) defaults to the session at the pointer; after "Pick another" it should
  offer the picked session too (the `queue.picked` event records it).
