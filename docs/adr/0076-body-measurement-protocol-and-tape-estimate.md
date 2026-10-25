# ADR-0074: One way to take each measurement, and a tape body-fat estimate

- Status: Accepted
- Date: 2026-10-25
- Deciders: Liam

## Context

Body measurements (2-B, #142) are typed on the Body page, the scale's weight can arrive from
Health Connect (ADR-0055), and a connected AI can propose them (ADR-0058). Nothing said how to
take them, so a waist read at the navel one week and at the narrowest point the next looks like
3 cm of change. Liam's brief of 25 Oct 2026 asked for consistent, repeatable measurements, a
neck and a scale's body fat, and a body-fat estimate from the tape shown as a trend. He decided
the open points the same day.

## Decision

**One protocol, in one place.** `domain/measurements.py` holds, for each kind, a `how` line
(bodyweight: same scale, hard floor, minimal clothing, the trend is the 7-day average; waist:
horizontal at the navel, relaxed; neck: just below the larynx, the tape sloping slightly down at
the front; chest: nipple line, arms down; upper arm: relaxed, midway between shoulder tip and
elbow point; thigh: standing, weight even, a set distance above the top of the kneecap; resting
heart rate: one source, the band overnight; body fat from a scale: same scale, barefoot, dry
feet, same time, trend only), a `CHECKLIST` (morning, after the toilet, before food, drink or
training; non-stretch tape on skin, snug and level; relaxed, read at the end of a normal breath
out; measure twice, a third time if more than 0.5 cm apart, enter the average; right side) and
a `CADENCE` (weight daily or weekly; tape and photos every 2-4 weeks). The web app reads them
from `GET /api/body/kinds` (`how`) and `GET /api/body/guide`; the AI reads them in the summary's
body section, which opens with "How these were measured", and in the tool descriptions
(`propose_log`'s measurement fields carry the unit, range and the first sentence of `how`).

**Two new kinds**: `neck` (cm, 20-70) and `body_fat_scale` (%, 3-60, one decimal). Both can be
typed and proposed; resting heart rate still can't be proposed. A test fails if a kind is
missing from the API's list, the specs, the re-measure thresholds, the proposable kinds, the
AI's schema, the summary or the export.

**Body settings** on `settings`, owner-only at `/api/account/body`: `height_cm` (120-230, empty
until set), `thigh_offset_cm` (5-30, default 15: the thigh's landmark, so its `how` names the
person's own distance) and `body_fat_estimate` (`off` by default, or `navy_male`). No sex field:
the only formula offered is the one for men, named as such.

**The estimate** (only with `navy_male` and a height): BF% = 495 / (1.0324 - 0.19077 *
log10(waist - neck) + 0.15456 * log10(height)) - 450, all in cm, to one decimal, from a waist
and a neck on the same day; nothing when either is missing or the waist isn't bigger than the
neck. It is worked out on read (`GET /api/body/estimates`) and never stored, so changing the
height or turning it off changes every point at once. It is labelled "estimate from waist and
neck, ±4%" wherever it shows: Body -> Latest and Progress (owner, after the brief), and the AI's
summary and `get_body` when the person shares body data. An AI can't propose it.

**Bodyweight's 7-day average** (`GET /api/body/averages`): for each day with a weigh-in, the
mean of the weigh-ins in the 7 days ending that day (it and the 6 before), with how many there
were, newest first. The first is the latest average; the rest are its trend. Worked out on
read, like the estimate. Days without a weigh-in get no point rather than a carried-forward one,
so a gap shows as a gap.

**Re-measure warnings, never a block.** A value this far from the last earlier entry of its
kind, of any age, is saved with a warning naming that day: bodyweight 2 kg, body fat from a
scale 3 points, waist and chest 3 cm, thigh 2 cm, upper arm and neck 1.5 cm, at or over the
threshold; resting heart rate isn't checked. "Waist is 3.5 cm off your last (12 Oct): different
landmark? Re-measure." For the scale's kinds the question is "different scale or time of day?".
`PUT /api/body` answers 200 with `{warnings}` instead of 204. A body proposal's card and its
Telegram message carry the same lines, worked out when shown, like "Replaces ...".

**What the AI hears.** `propose_log`'s answer adds the warnings ("The card also says: ...")
only when the connection has `body:read`: they tell of earlier measurements, which ADR-0058
keeps from an AI that may only propose.

**Cut.** Importing body fat from Health Connect: Mi Fitness doesn't write weight or body fat to
Health Connect (`docs/runbooks/band-import.md`), and our reader (ADR-0070) reads only steps and
heart rate while it is on trial. Manual entry only; importing `BodyFatRecord` like bodyweight
(same fill rules) is a follow-up once a source writes it.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Protocol in the domain, served to every reader (chosen) | One text for the web, the AI and its tools; tested | The web can't reword a field's hint on its own |
| Instructions written in the web app | Quick | The AI and the web drift apart |
| Store the estimate as a measurement | Simple reads | Stale after a height change; looks measured; proposable by mistake |
| Refuse a far value | Stops typos | A real change can't be saved; the range check already catches slips |
| Compare with the last 30 days only | Fewer old comparisons | After a gap nothing is checked, which is when landmarks drift most |

## Consequences

- The web PR shows the checklist, the per-field hints, the warnings after Save, the estimate
  on Body -> Latest and Progress and the 7-day average; and the body settings on Account.
- The AI guide (`docs/ai-guide.md`) is at version 2: it explains the new kinds and the estimate.
- The migration rebuilds `measurements`' kind check; its downgrade refuses while neck or scale
  body-fat rows exist.
- A formula for women (or another one) is a new value of `body_fat_estimate`, not a sex field.
