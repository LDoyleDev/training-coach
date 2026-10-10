# ADR-0046: Readiness questions that advise, not block

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

The plan has hard efforts: all-out intervals (the High-intensity session) and test days with
max efforts and the 12-minute run. Before others use the app, it should ask the questions a
pre-exercise screen asks, so someone with a heart condition, chest pain or fainting hears "ask a
doctor first" before the hardest work. The best-known form (PAR-Q+) is copyrighted; its topics
aren't.

## Decision

- **Seven yes-or-no questions in our own words** (`domain/readiness.py`): heart condition or high
  blood pressure, chest pain, fainting or dizziness, medication for a long-term condition, another
  condition that makes hard exercise unsafe, a bone or joint problem, pregnancy. Answered on a
  Readiness page; asked again after about 6 months, or when the questions change (`VERSION`).
- **It advises; it never blocks.** On a hard day (the `hiit` session or a test day), Today shows
  a note: answer the questions if they're due, or "check with a doctor before hard efforts like
  this one" if any answer is yes. Easy days say nothing.
- **Stored as health data:** one row per person (`readiness_answers`, the latest answers only),
  in the export, erased with everything else, never logged.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Own questions, advise (chosen) | No licence question; the person stays in charge; nothing stops a session | Someone can ignore the advice |
| Own questions, gate hard work until a doctor is confirmed | Stronger | A tick box proves nothing, and blocking pushes people to lie or leave |
| Use the PAR-Q+ text | Recognised | Copyrighted wording; its follow-up pages are long for a phone |

## Consequences

- The privacy notice lists the answers as health data under consent (draft in `docs/legal/`).
- Which sessions count as hard is `HARD_SESSIONS` plus test days; a new all-out session in the
  plan needs adding there.
- This isn't medical advice and doesn't replace it; the page says so.
