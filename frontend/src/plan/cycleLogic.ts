/**
 * The person's own cycle, edited as a draft (ADR-0093), a TS copy of `domain/cycle.py`. The
 * browser works out Add's suggestion, the limits and the "Saving will" list from the same rules
 * Save checks again on the server; both copies read `plan/cycle-cases.json`. A cycle is its
 * sessions in queue order, each with the rest places after it (ADR-0091). A saved session is
 * keyed by its id, a new one by the draft's own key ("n1") until Save gives it an id.
 */

/** A saved session's id, or a new session's key in the draft. */
export type Key = number | string

export const MAX_SESSIONS = 10 // Decided 13
export const MAX_DAYS = 14 // Decided 13: the cycle's days, its rest places included
export const MAX_REST = 6 // rest places after one session, as session_templates' check

/** One session of the cycle and the rest places after it. */
export interface Slot {
  key: Key
  restAfter: number
}

export type Cycle = readonly Slot[]

/** Where the queue stands: the next session, and sessions queued before the cycle resumes, as
 * `domain/queue.py`'s `Position`. */
export interface Position {
  pointer: number
  queued: readonly number[]
}

/** The rest places still to come `gone` days after a session with `restAfter` rest places was
 * done (ADR-0091), a TS copy of `domain/queue.py`'s `rest_days_left`. 0: a day for the next
 * session, or the day it was done. */
export function restDaysLeft(restAfter: number, gone: number): number {
  if (gone < 1) return 0
  return Math.max(0, restAfter - gone + 1)
}

/** How many days the cycle takes: a day per session and one per rest place. */
export function days(cycle: Cycle): number {
  return cycle.reduce((n, s) => n + 1 + s.restAfter, 0)
}

/** Where a new session goes (Decided 1): after the session with the most rest days after it, the
 * later one on a tie, so the last session when none has any. */
export function suggestedAfter(cycle: Cycle): Key {
  if (cycle.length === 0) throw new Error('the cycle has no sessions')
  const most = Math.max(...cycle.map((s) => s.restAfter))
  return cycle.findLast((s) => s.restAfter === most)!.key
}

/** The rest places either side of a new session added after one with `restAfter` (Decided 1).
 * With 1 or more it takes one of them, and of the rest the session before keeps the larger half,
 * so the cycle keeps its length: 1 gives both 0, 3 gives both 1. With 0 (the owner's sessions)
 * both get 0 and the cycle is a day longer. */
export function split(restAfter: number): [number, number] {
  if (restAfter < 1) return [0, 0]
  const left = restAfter - 1
  return [left - Math.floor(left / 2), Math.floor(left / 2)]
}

/** The cycle with a new session after `after` (the suggestion when null), the rest places after
 * that session split around it. */
export function add(cycle: Cycle, key: string, after: Key | null = null): Slot[] {
  const at = index(cycle, after ?? suggestedAfter(cycle))
  const [before, fresh] = split(cycle[at].restAfter)
  return [
    ...cycle.slice(0, at),
    { ...cycle[at], restAfter: before },
    { key, restAfter: fresh },
    ...cycle.slice(at + 1),
  ]
}

/** The cycle without `key` (Decided 6): its day and rest places go to the session before it, the
 * last one if it was first, so the cycle keeps its length up to MAX_REST. */
export function remove(cycle: Cycle, key: Key): Slot[] {
  const at = index(cycle, key)
  const rest = cycle.filter((s) => s.key !== key)
  if (rest.length === 0) return []
  // The session before it, wrapping to the last (JS's % keeps the sign, Python's doesn't).
  const before = (at - 1 + rest.length) % rest.length
  const gets = Math.min(MAX_REST, rest[before].restAfter + 1 + cycle[at].restAfter)
  rest[before] = { ...rest[before], restAfter: gets }
  return rest
}

/** The cycle with `key` moved `by` places (-1 Up, +1 Down, Decided 8), its rest places with it;
 * held at either end. */
export function move(cycle: Cycle, key: Key, by: number): Slot[] {
  const at = index(cycle, key)
  const to = Math.min(Math.max(at + by, 0), cycle.length - 1)
  const rest = cycle.filter((s) => s.key !== key)
  rest.splice(to, 0, cycle[at])
  return rest
}

/** The cycle with `restAfter` rest places after `key`. */
export function withRest(cycle: Cycle, key: Key, restAfter: number): Slot[] {
  const at = index(cycle, key)
  return cycle.map((s, i) => (i === at ? { ...s, restAfter } : s))
}

/** Why the cycle can't be saved (Decided 13), in words; null when it can. */
export function problem(cycle: Cycle): string | null {
  const keys = cycle.map((s) => s.key)
  if (cycle.length === 0) return 'Your cycle needs at least one session.'
  if (new Set(keys).size < keys.length) return 'A session can be in your cycle only once.'
  if (cycle.length > MAX_SESSIONS) return `A cycle can have at most ${MAX_SESSIONS} sessions.`
  if (cycle.some((s) => !(s.restAfter >= 0 && s.restAfter <= MAX_REST)))
    return `Rest days after a session can be 0 to ${MAX_REST}.`
  if (days(cycle) > MAX_DAYS)
    return `Your cycle would be ${days(cycle)} days; it can be at most ${MAX_DAYS}.`
  return null
}

/** Why Add is greyed (Decided 13), in words; null when a session can be added. Only the count can
 * stop it: at the suggested place a new session takes a rest place when there is one, and a cycle
 * with none is a day per session, at most MAX_SESSIONS. */
export function cannotAdd(cycle: Cycle): string | null {
  if (cycle.length >= MAX_SESSIONS)
    return `You have ${MAX_SESSIONS} sessions, the most a cycle can have.`
  return null
}

/** A draft as Save writes it: the sessions in their new order (a position each), and the queue
 * after it (Decided 9). */
export interface Applied {
  cycle: Slot[]
  pointer: Key // the session the queue offers next; a new one's key until Save gives it an id
  queued: number[] // a swap's sessions still to come before the cycle resumes
  added: string[] // new sessions, in cycle order
  removed: number[] // saved sessions not in the draft, in the old order
  moved: number[] // saved sessions moved: the fewest that explain the new order
  lastRest: number | null // the rest places after the session done last; null: none done
  changed: boolean // anything differs: a session added, removed or moved, or a rest place
  days: number
  positions: Map<Key, number> // a Map, so the id 1 and a key "1" stay apart
}

const saved = (k: Key): k is number => typeof k === 'number'
const fresh = (k: Key): k is string => typeof k === 'string'

/** `draft` in place of the saved cycle `before`, with the queue at `position` and `lastDone` the
 * planned session done or rested last (ADR-0091), if any.
 *
 * The pointer stays on its session (Decided 8 and 9) except in two cases. Its session is removed:
 * it moves to the next session left, the swap's first if one is queued, else the next after it
 * in the old order. A new session is added straight after the one done last, where the queue
 * stands: the new session is next, or it would wait a whole cycle. `queued` drops removed
 * sessions. */
export function applied(
  before: Cycle,
  draft: Cycle,
  position: Position,
  lastDone: number | null,
): Applied {
  const reason = problem(draft)
  if (reason !== null) throw new Error(reason)
  const old = before.map((s) => s.key)
  const now = draft.map((s) => s.key)
  const unknown = now.filter((k) => saved(k) && !old.includes(k))
  if (unknown.length > 0) throw new Error(`session ${unknown[0]} is not in the plan`)
  const kept = now.filter(saved)
  let queued = position.queued.filter((k) => kept.includes(k))
  const pointer = pointerAfter(old, now, position.pointer, queued, lastDone)
  if (queued.length > 0 && pointer === queued[0] && !now.includes(position.pointer))
    queued = queued.slice(1) // the swap's first took the removed session's place
  // The draft's where it has one.
  const rests = new Map<Key, number>([...before, ...draft].map((s) => [s.key, s.restAfter]))
  return {
    cycle: [...draft],
    pointer,
    queued,
    added: now.filter(fresh),
    removed: old.filter(saved).filter((k) => !now.includes(k)),
    moved: movedOf(
      old.filter(saved).filter((k) => kept.includes(k)),
      kept,
    ),
    lastRest: lastDone === null ? null : (rests.get(lastDone) ?? null),
    changed: !same(before, draft),
    days: days(draft),
    positions: new Map(draft.map((s, i) => [s.key, i])),
  }
}

const same = (a: Cycle, b: Cycle) =>
  a.length === b.length && a.every((s, i) => s.key === b[i].key && s.restAfter === b[i].restAfter)

function pointerAfter(
  old: readonly Key[],
  now: readonly Key[],
  pointer: number,
  queued: readonly number[],
  last: number | null,
): Key {
  if (
    last !== null &&
    now.includes(last) &&
    old.includes(last) &&
    pointer === old[(old.indexOf(last) + 1) % old.length]
  ) {
    const after = now[(now.indexOf(last) + 1) % now.length]
    if (fresh(after)) return after
  }
  if (now.includes(pointer)) return pointer
  if (queued.length > 0) return queued[0]
  const at = old.indexOf(pointer)
  if (at >= 0) {
    const found = [...old.slice(at + 1), ...old.slice(0, at)].find((k) => now.includes(k))
    if (found !== undefined) return found
  }
  return now[0]
}

/** The sessions off a longest run kept in the old order: the fewest moves that turn `old` into
 * `now` (both the same sessions). On a tie the later-placed session is the one that stayed, so
 * A B C to B A C reads as B moved up. */
function movedOf(old: readonly number[], now: readonly number[]): number[] {
  const ranks = now.map((k) => old.indexOf(k))
  const best: number[][] = [] // best[i]: a longest increasing run of ranks ending at i
  ranks.forEach((rank, i) => {
    let run: number[] = []
    // From the nearest back, keeping the first of the longest, as Python's max.
    for (let j = i - 1; j >= 0; j--)
      if (ranks[j] < rank && best[j].length > run.length) run = best[j]
    best.push([...run, i])
  })
  let stayed: number[] = []
  // The longest, the one ending latest on a tie.
  for (const run of [...best].reverse()) if (run.length > stayed.length) stayed = run
  return now.filter((_, i) => !stayed.includes(i))
}

function index(cycle: Cycle, key: Key): number {
  const at = cycle.findIndex((s) => s.key === key)
  if (at < 0)
    throw new Error(`session ${typeof key === 'string' ? `'${key}'` : key} is not in the cycle`)
  return at
}
