/**
 * The cycle card's draft (ADR-0093): each session of the cycle as it should be saved, in queue
 * order. A saved session is keyed by its place in the loaded list, a new one by its draft key
 * ("n1"), so `cycleLogic` can tell them apart. Nothing is saved until Save.
 */

import type { CycleEntry, EditSession, Place } from '../api'
import { landing } from '../walkthrough/days'
import {
  add,
  applied,
  days,
  move,
  remove,
  withRest,
  type Applied,
  type Key,
  type Slot,
} from './cycleLogic'

export type Kind = EditSession['kind']

export interface Entry extends Slot {
  slug: string // a saved session's, or a new one's "new:n1", as its versions name it
  name: string
  kind: Kind
  copyOf: string | null // a new session copied from this saved one's versions
  logged: number // workouts naming it, so Remove can say what happens to them
}

export const NEW = 'new:'

/** The kinds a person picks from, each with what it changes (Decided 3). */
export const KINDS: { kind: Kind; label: string; line: string }[] = [
  { kind: 'strength', label: 'Strength', line: 'A warm-up first. On a short day it’s cut to fit.' },
  {
    kind: 'conditioning',
    label: 'Cardio',
    line: 'Its cardio first, the rest after the run. On a short day it’s cut to fit.',
  },
  { kind: 'recovery', label: 'Recovery', line: 'No warm-up, and never cut short.' },
]

export const kindLabel = (kind: Kind) => KINDS.find((k) => k.kind === kind)?.label ?? kind

export function cycleOf(sessions: EditSession[]): Entry[] {
  return sessions.map((s, i) => ({
    key: i,
    restAfter: s.rest_after,
    slug: s.slug,
    name: s.name,
    kind: s.kind,
    copyOf: null,
    logged: s.logged,
  }))
}

/** The cycle rules keep only keys and rest places: each slot gets its entry back. */
function merged(cycle: Entry[], slots: Slot[], fresh?: Entry): Entry[] {
  return slots.map((s) => ({
    ...(cycle.find((e) => e.key === s.key) ?? fresh!),
    restAfter: s.restAfter,
  }))
}

/** The cycle with a new session after `after`, the rest places split around it (Decided 1). */
export function added(cycle: Entry[], entry: Entry, after: Key): Entry[] {
  return merged(cycle, add(cycle, String(entry.key), after), entry)
}

export const rested = (cycle: Entry[], key: Key, restAfter: number) =>
  merged(cycle, withRest(cycle, key, restAfter))

/** Up (-1) or Down (+1), its rest places with it (Decided 8). */
export const moved = (cycle: Entry[], key: Key, by: number) => merged(cycle, move(cycle, key, by))

/** Without it, its days to the session before it (Decided 6). */
export const removed = (cycle: Entry[], key: Key) => merged(cycle, remove(cycle, key))

/** What Remove asks first, by its history (Decided 5). */
export function removeQuestion(entry: Entry): string {
  if (entry.logged === 0) return `Remove ${entry.name}? Nothing is logged for it, so it goes.`
  const days =
    entry.logged === 1 ? 'Its 1 logged day stays' : `Its ${entry.logged} logged days stay`
  return `Remove ${entry.name}? ${days} in your history under its name.`
}

export const renamed = (cycle: Entry[], key: Key, name: string) =>
  cycle.map((e) => (e.key === key ? { ...e, name } : e))

/** The next free draft key: "n1", "n2", ... */
export function newKey(cycle: Entry[]): string {
  const used = cycle.map((e) => (typeof e.key === 'string' ? Number(e.key.slice(1)) : 0))
  return `n${Math.max(0, ...used) + 1}`
}

/** A name no session of the cycle has: `base` itself when `first`, else "Legs 2", "Legs 3". */
export function freeName(base: string, cycle: Entry[], first: boolean): string {
  const taken = new Set(cycle.map((e) => e.name.trim().toLowerCase()))
  if (first && !taken.has(base.toLowerCase())) return base
  const stem = first ? base : base.replace(/ \d+$/, '') // a copy of "Legs 2" is "Legs 3"
  for (let n = 2; ; n++) if (!taken.has(`${stem} ${n}`.toLowerCase())) return `${stem} ${n}`
}

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`

export const thenRest = (n: number) =>
  n === 0 ? 'then no rest days' : `then ${plural(n, 'rest day')}`

const DAY_MS = 86_400_000

/** "Your cycle, 7 days: A, rest, B, rest, C, rest, rest." (Decided 4), each session on the day
 * the rest places before it land it, as the walk-through lands a starter's. */
export function weekLine(cycle: Entry[], lead = 'Your cycle'): string {
  const start = new Date(2026, 0, 5)
  const line = Array<string>(days(cycle)).fill('rest')
  landing(
    start,
    cycle.map((e) => e.restAfter),
  ).forEach((day, i) => {
    line[Math.round((day.getTime() - start.getTime()) / DAY_MS)] = cycle[i]!.name
  })
  return `${lead}, ${plural(line.length, 'day')}: ${line.join(', ')}.`
}

/** When the cycle isn't a week, how often each session comes round (Decided 4). */
export function lengthLine(n: number): string | null {
  if (n === 7) return null
  return `Each session comes round ${n > 7 ? 'less' : 'more'} often than once a week.`
}

/** Whether the cycle differs from what was loaded: only then is it sent. */
export function cycleChanged(cycle: Entry[], sessions: EditSession[]): boolean {
  return (
    cycle.length !== sessions.length ||
    cycle.some((e, i) => {
      const s = sessions[i]!
      return (
        e.slug !== s.slug || e.name !== s.name || e.kind !== s.kind || e.restAfter !== s.rest_after
      )
    })
  )
}

/** The cycle as Save and the draft map take it. */
export function cycleBody(cycle: Entry[]): CycleEntry[] {
  return cycle.map((e) => {
    const common = { name: e.name.trim(), kind: e.kind, rest_after: e.restAfter }
    return typeof e.key === 'string'
      ? { new: e.key, ...common, copy_of: e.copyOf }
      : { slug: e.slug, ...common }
  })
}

/** What each session's versions are before any edit: a new one's are its copy's, or none. */
export function baselines(
  cycle: Entry[],
  sessions: EditSession[],
): (Pick<EditSession, Place> & { slug: string })[] {
  return cycle.map((e) => {
    const from = sessions.find((s) => s.slug === (e.copyOf ?? e.slug))
    return { slug: e.slug, home: from?.home ?? [], gym: from?.gym ?? [], away: from?.away ?? [] }
  })
}

const NOTE_MAX = 120 // PlanChanges.note

/** What Save would change in the cycle, a line each, and the note it prefills (Decided 9 and 10,
 * ADR-0073). Null when the cycle is as loaded. */
export interface Saving {
  lines: string[]
  note: string
}

const restAfter = (n: number) => (n === 0 ? 'no rest days' : plural(n, 'rest day'))

export function savingWill(cycle: Entry[], sessions: EditSession[]): Saving | null {
  if (!cycleChanged(cycle, sessions)) return null
  const before = cycleOf(sessions)
  const was = Math.max(
    0,
    sessions.findIndex((s) => s.next),
  )
  const position = { pointer: was, queued: [] }
  // Decided 9's exception turns on the session done last, which the edit view doesn't say. The
  // only one it can be is the session before the next, so both outcomes are worked out.
  const last = (was - 1 + before.length) % before.length
  let now: Applied
  let ifLast: Applied
  try {
    now = applied(before, cycle, position, null)
    ifLast = applied(before, cycle, position, last)
  } catch {
    return null // over a limit: the card says why
  }
  const name = (k: Key) => cycle.find((e) => e.key === k)?.name ?? sessions[k as number]!.name
  const said: [string, string][] = [] // the line, and its words in the note
  cycle.forEach((e, i) => {
    if (typeof e.key === 'string') {
      const where = i === 0 ? 'first' : `after ${cycle[i - 1]!.name}`
      said.push([
        `Add ${e.name} ${where}, with ${restAfter(e.restAfter)} after it`,
        `added ${e.name}`,
      ])
      return
    }
    const s = sessions[e.key]!
    if (e.name !== s.name)
      said.push([`Rename ${s.name} to ${e.name}`, `renamed ${s.name} to ${e.name}`])
    if (now.moved.includes(e.key))
      said.push([`Move ${e.name} to place ${i + 1}`, `moved ${e.name}`])
    if (e.kind !== s.kind) {
      const kind = kindLabel(e.kind).toLowerCase()
      said.push([`Make ${e.name} a ${kind} session`, `made ${e.name} a ${kind} session`])
    }
    if (e.restAfter !== s.rest_after)
      said.push([
        `Give ${e.name} ${restAfter(e.restAfter)} after it`,
        `${e.name} now has ${restAfter(e.restAfter)} after it`,
      ])
  })
  for (const k of now.removed) said.push([`Remove ${name(k)}`, `removed ${name(k)}`])
  const next =
    now.pointer === ifLast.pointer
      ? now.pointer === was
        ? `Next stays ${name(was)}`
        : `Next: ${name(now.pointer)}, instead of ${name(was)}`
      : `Next: ${name(ifLast.pointer)} if ${name(last)} was your last session, else ${name(now.pointer)}`
  const joined = said.map(([, words]) => words).join('; ')
  const note = joined.length > NOTE_MAX ? `${said.length} changes to your sessions` : joined
  return {
    lines: [...said.map(([line]) => line), next],
    note: note.charAt(0).toUpperCase() + note.slice(1),
  }
}
