import type { FlowMove as Move } from '../api'

/** The guided mobility flow's clock (ADR-0062), also guided stretching's (ADR-0032 addendum).
 * Pure: the player feeds it seconds. */

/** One movement's place on the flow's timeline, in seconds. `half` is the side switch of a
 * one-sided movement. */
export type Section = { index: number; start: number; end: number; half: number | null }

export const NEXT_UP = 5 // seconds of "Next: …" over the end of a movement
export const COUNT_IN = 3 // short sounds before the next movement
export const BACK_GRACE = 2 // Back this soon after a start goes to the movement before

export function schedule(moves: Move[]): Section[] {
  let start = 0
  return moves.map((m, index) => {
    const length = m.per_side ? m.seconds * 2 : m.seconds
    const section = {
      index,
      start,
      end: start + length,
      half: m.per_side ? start + m.seconds : null,
    }
    start += length
    return section
  })
}

export function totalSeconds(sections: Section[]): number {
  return sections.length ? sections[sections.length - 1].end : 0
}

export type At = {
  index: number
  done: boolean
  left: number // whole seconds left on this side, or this movement
  side: 1 | 2 | null
  nextUp: boolean // the last NEXT_UP seconds of a movement that has one after it
}

/** Where the flow is at `t` seconds. */
export function at(sections: Section[], t: number): At {
  const total = totalSeconds(sections)
  if (t >= total)
    return { index: sections.length - 1, done: true, left: 0, side: null, nextUp: false }
  const s = sections.find((x) => t < x.end) ?? sections[0]
  const side = s.half === null ? null : t < s.half ? 1 : 2
  const until = side === 1 && s.half !== null ? s.half : s.end
  return {
    index: s.index,
    done: false,
    left: Math.ceil(until - t),
    side,
    nextUp: s.index < sections.length - 1 && s.end - t <= NEXT_UP,
  }
}

export type Cue = 'count' | 'switch' | 'next' | 'finish'

/** What to play for the time from `from` to `to` (later), in order: a switch at a one-sided
 * movement's half, three counts before each movement ends, then next, or finish at the end. */
export function cues(sections: Section[], from: number, to: number): Cue[] {
  const crossed = (mark: number) => from < mark && mark <= to
  const found: [number, Cue][] = []
  sections.forEach((s, i) => {
    if (s.half !== null && crossed(s.half)) found.push([s.half, 'switch'])
    for (let n = COUNT_IN; n >= 1; n--) if (crossed(s.end - n)) found.push([s.end - n, 'count'])
    if (crossed(s.end)) found.push([s.end, i === sections.length - 1 ? 'finish' : 'next'])
  })
  return found.sort((a, b) => a[0] - b[0]).map(([, cue]) => cue)
}

/** Where Skip or Back goes from `t`: Skip to the next movement's start (or the end); Back to
 * this movement's start, or the one before if this one has only just started. */
export function jump(sections: Section[], t: number, direction: 'back' | 'forward'): number {
  const here = at(sections, t)
  const s = sections[here.index]
  if (direction === 'forward') return here.done ? totalSeconds(sections) : s.end
  if (here.done) return sections[sections.length - 1].start
  if (t - s.start < BACK_GRACE && here.index > 0) return sections[here.index - 1].start
  return s.start
}

/** Whole minutes moved, as logged: nearest, and at least 1 once there was any. */
export function minutesDone(seconds: number): number {
  return seconds > 0 ? Math.max(1, Math.round(seconds / 60)) : 0
}

/** "1:05" for a countdown. */
export function clock(seconds: number): string {
  const s = Math.max(0, seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// ------------------------------------------------ guided stretching (ADR-0032 addendum)

/** A stretch as the timeline needs it: its rounds, on each side when one-sided. */
export type StretchStep = { rounds: number; per_side: boolean }
export type StretchTiming = { hold: number; position: number; release: number }

/** What a stretch's time is spent on: getting into position (into the stretch, or onto its
 * other side), holding, or letting go between rounds on the same side. */
export type Kind = 'position' | 'hold' | 'release'

/** One stretch of time, as a `Section` so `at` and `totalSeconds` read it. `stretch` is the
 * step's index, `side` 1 or 2 for a one-sided stretch, `round` from 1. */
export type Part = Section & { kind: Kind; stretch: number; side: 1 | 2 | null; round: number }

/** The stretching timeline: every position, hold and release in order (`parts`), and each
 * stretch as one `Section` (`stretches`, its second side at `half`) for the stretch on screen,
 * "Next: …", Back and Skip. Its total is what the routine was built to fit. */
export function stretchSchedule(
  steps: StretchStep[],
  timing: StretchTiming,
): { parts: Part[]; stretches: Section[] } {
  const parts: Part[] = []
  const stretches: Section[] = []
  let t = 0
  const add = (kind: Kind, length: number, stretch: number, side: 1 | 2 | null, round: number) => {
    const index = parts.length
    parts.push({ index, start: t, end: t + length, half: null, kind, stretch, side, round })
    t += length
  }
  steps.forEach((step, stretch) => {
    const start = t
    let half: number | null = null
    for (const side of step.per_side ? ([1, 2] as const) : [null]) {
      if (side === 2) half = t
      add('position', timing.position, stretch, side, 1)
      for (let round = 1; round <= step.rounds; round++) {
        if (round > 1) add('release', timing.release, stretch, side, round)
        add('hold', timing.hold, stretch, side, round)
      }
    }
    stretches.push({ index: stretch, start, end: t, half })
  })
  return { parts, stretches }
}

/** What to play for the time from `from` to `to` (later), in order: at each change a sound
 * for what starts (a new stretch: next; the other side: switch; a hold: next; letting go: a
 * count), then finish at the end. Nothing at the very start: tapping Start is the start. */
export function stretchCues(parts: Part[], from: number, to: number): Cue[] {
  const crossed = (mark: number) => from < mark && mark <= to
  const found: Cue[] = []
  for (const p of parts) {
    if (!crossed(p.start)) continue
    if (p.kind === 'hold') found.push('next')
    else if (p.kind === 'release') found.push('count')
    else found.push(p.side === 2 ? 'switch' : 'next')
  }
  if (parts.length && crossed(totalSeconds(parts))) found.push('finish')
  return found
}

/** "9 min 55 s", or "10 min" on the minute. */
export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m === 0) return `${s} s`
  return s ? `${m} min ${s} s` : `${m} min`
}
