# ADR-0069: Plan gets its own tab, Tests moves into Body, and each session has its own body map

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

The bottom nav was Home, Today, Progress, Tests, Body, Account, with the Plan as a tab of
Progress (`docs/specs/ux-flow-plan.md` D2). Since the body map (#285) and the exercise catalogue
(ADR-0064), the plan is where a person looks to see what their training covers, so it was two
taps away. Tests is used a few times a year (baseline and retests, ADR-0037), and it took a nav
slot of its own.

The body map shows the whole week. Opening one session on the Plan page showed only its
exercise table, not what that session works.

## Decision

- **Nav, phone and desktop:** Home, Plan, Progress, Today, Body, Account. Today keeps
  `/session`. Plan is `/plan`, its own page. The old `/progress?tab=plan` now goes to `/plan`, and
  Progress has no tabs.
- **Tests is the second tab of Body** (Measurements | Tests, kept in the address as
  `/body?tab=tests`). `/tests` still works: it opens that tab, so bookmarks and older bot messages
  land there. The bot's links and its "where to enter results" text point at `/body?tab=tests`.
  The Body and Tests pages take an `embedded` flag and drop their own frame inside the tabs
  (`Frame` in `components/AppShell.tsx`).
- **Each session's own map.** An open session on the Plan page shows, at the top of its row, the
  front and back figures coloured by how hard *that session* works each muscle, then a chip per
  muscle with its sets. Tapping a muscle on the figure or its chip says how many of its sets come
  from this session and from which exercises. The week's map moves to the bottom of the page as
  the overall picture.
- **One session's colour scale is its own, not the week's bands.** A band (green = on target)
  is about a week. One session is never on target by itself, so the session map uses a heat
  scale (`domain.coverage.Heat`), with the thresholds the coverage rules already use:

  | Heat | Sets in the session | Why the cut |
  | --- | --- | --- |
  | Not worked | 0 | |
  | A little | under 2 | `DAY_SETS`: under 2 it doesn't make the session a day for the muscle |
  | Worked | 2 up to 6 | counts as a day |
  | Worked hard | 6 up to 11 | `HARD_FROM` to `SESSION_CAP`: one session's productive range (research file) |
  | Too much for one session | over 11 | `SESSION_CAP`, the same warning colour as the week's "Too much" |

  The colours are an orange ramp (`--heat-*`), so they can't be read as the week's greens.
- **Computed on the server.** `GET /api/plan/coverage` adds each session's `slug` and `muscles`
  (muscle, fractional sets, heat; only the muscles it works, main ones first) and `hard_from`.
  The page fetches it once, for the week's map and every session's.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Heat scale cut at the existing day and session thresholds (chosen) | Says what one session does; reuses rules the week's map already uses; no new evidence claims | A second legend to learn |
| Colour a session by the week's bands | One legend | Misleading: a session's 7 sets would read "below the minimum" or "on target" for a week it isn't |
| Scale relative to the session's busiest muscle | Always uses the full ramp | Not comparable between sessions: a light day looks as red as a heavy one |
| Tests as its own page with no nav entry | Less nesting | Hard to find; Body is where the measuring already is |
| Seven tabs | Keeps Tests | Doesn't fit 360 px with readable labels |

## Consequences

- Six tabs still fit a 360 px phone (`grid-cols-6`, labels 13 px). Plan replaces Tests in the
  count.
- `SessionLoadView` grew `slug` and `muscles`: the API types are regenerated, and the Plan page's
  session rows match coverage by slug.
- Tests' headings stay as they were inside the Body tab; Body's own heading is shown once.
- `ux-flow-plan.md` D2 and `dashboard-design.md` now point here.

## Addendum (28 Oct 2026): home or gym

The page's maps count one place's versions of the sessions, with Home | Gym for someone who
trains at both, and fetch again when it changes (ADR-0071, "Built (the body map's place)").
