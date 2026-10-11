# ADR-0056: Keep the weekly AI comment 7 days, for the web review

- Status: Accepted
- Date: 2026-10-11
- Deciders: Liam

## Context

The weekly AI comment (ADR-0047 B) was made once per weekly review, sent on Telegram and never
stored (`docs/specs/ai-connections.md` B). The web review page (`/review`, ux-flow-plan C4) could
only say the comment went to Telegram. Liam wants to read it on the web too, under the review it
belongs to, without paying for a second AI call.

## Decision

This replaces only the "never stored" rule of ADR-0047 B; the rest of ADR-0047 stands.

- **Keep the comment the bot already made.** After the weekly review, the cleaned comment
  (`services.ai_comment.clean`: no control characters, links, mentions or commands; at most
  1,200 characters) is stored per person with its week (the Monday) and when it was made
  (`ai_comments`, one row per person and week; a check constraint caps the length). The label
  is not stored.
- **Still one AI call per weekly review**, and only then. Opening the page never calls Groq.
- **Kept 7 days.** Rows older than 7 days are deleted at each weekly review (whether or not a
  comment comes that week) and whenever a new one is stored; a row past its 7 days is never
  shown, even before it is deleted.
- **Shown on `/review` for its week**, under the review, labelled "AI comment (from your Groq
  key, a suggestion only)". Only while comments are on; with comments off or nothing kept the
  page shows its note instead. `GET /api/review` returns it as `ai_comment`, a plain string.
- **Untrusted LLM output** (ADR-0007): the web renders it as text only, never as HTML or
  markdown. It is never acted on.
- **Never shared**: not on the `/share` picture (ADR-0050), not in "Copy for my AI" or MCP
  answers.
- **The person's data**: in the export (`ai_comments`), deleted with everything on erase
  (ADR-0044: the `user_id` cascade).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Keep the bot's comment 7 days (chosen) | No extra AI call; the page shows what Telegram got; short retention | AI text about the person's training is now stored |
| Make a new comment when the page opens | Nothing stored | A second AI call per view, on the person's quota; comments differ between Telegram and the web |
| Keep it until erased | Every past week has its comment | Stored for longer than it is useful; more to protect |
| Keep the note only (as before) | Nothing stored | The comment is only on Telegram |

## Consequences

- New per-person table `ai_comments` (migration `7281a9439e79`); in the export, erased with
  the person.
- `docs/specs/ai-connections.md` B, `docs/architecture.md`, the threat model and the privacy
  notice draft say it is kept 7 days, no longer "never stored".
- In the worst case (no weekly review runs, e.g. the bot is paused for weeks) a row stays in
  the database past 7 days until the next review, but is never shown after its 7 days.
