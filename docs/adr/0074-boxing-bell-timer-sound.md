# ADR-0074: A boxing-ring bell is everyone's timer sound, for every guided timer

- Status: Accepted (amends ADR-0062)
- Date: 2026-10-25
- Deciders: Liam

## Context

ADR-0062 added a chosen sound for the mobility flow, chime to start. Liam asked (25 Oct) for "a
ding ding notification instead of just the vibration ... when sets start or change or timers
end, to the sound of like a bell in a boxing ring". The rest timer and guided stretching had no
chosen sound, and the setting only spoke of the mobility flow.

## Decision

- A new timer sound, **Boxing bell** (`ring`), synthesised in the browser like the others: a
  bright brass dome, struck hard, with a beating near-twin of its fundamental and clangy high
  partials that die first. A side switch (or any small change) is one strike, the next thing
  starting (a movement, a set after a rest) is "ding-ding", the end is three strikes, and the
  3-2-1 count is a soft tick. Headroom is kept so three strikes don't clip.
- `ring` is the default for everyone: the column's server default and the service's default.
  The migration moves rows still on the old default, `chime`, to `ring`; any other choice is
  kept. There is one person today and he asked for it; a chosen chime can't be told apart from
  the default one, so it moves too. Downgrading moves `ring` back to `chime`.
- The setting is one **Timer sound**, used by every guided timer: rest end, the mobility flow
  and guided stretching. It is listed with the boxing bell first; tapping one plays it.
- Addendum (27 Oct 2026): the end of a whole session has its own louder, celebratory voice in
  each sound (`playSessionEnd`): four quick notes up a major chord, then "ding-ding" on the
  octave left to ring out, on a hotter bus through a limiter. It rings once when a guided
  session is saved, when HIIT, the mobility flow closing a session or guided stretching runs to
  its end, and when cardio or stretching is logged by a tap; 'none' stays silent. A timer's
  own `finish` (three strikes) is kept for a timer that doesn't end the session.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| New `ring` sound, default for all, old defaults moved (chosen) | What was asked; one setting everywhere | A chime chosen on purpose also moves (one person, who asked) |
| New `ring` sound, default only for new rows | Never changes a stored value | The one person asking would still hear the chime |
| Recorded bell sample | Most realistic | An audio file to ship and licence; the others are synthesised |
| Re-voice the existing `bell` | No new value | Changes a sound someone may have chosen |

## Consequences

- The guided timers (rest end in the session screen, the flow player, guided stretching) read
  `settings.sound` and call `playChange(sound, change)` with `count`, `switch`, `next` or
  `finish`; before the setting loads they use `DEFAULT_SOUND` (`ring`).
- A new sound means a value in `Sound`, a migration for the check constraint, a voice for every
  change in `VOICES` (a test checks each), and a label in Settings (a `Record`, so the compiler
  checks it).
