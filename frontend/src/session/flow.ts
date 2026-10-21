import type { FlowMove as Move } from '../api'

/** The guided mobility flow's clock (ADR-0062). Pure: the player feeds it seconds. */

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
