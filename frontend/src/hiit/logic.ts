/**
 * The HIIT timer's schedule, as pure functions of the settings and the elapsed time. The model
 * follows the "Tabata Timer" app: prepare, then sets of work/rest cycles with a longer rest
 * between sets, then an optional cool down.
 */

export type HiitSettings = {
  /** The "Get ready" count before the first work, in seconds (0: none). */
  prepare: number
  work: number
  /** Rest between cycles inside a set (0: back-to-back work). */
  rest: number
  /** Work + rest pairs in each set. */
  cycles: number
  sets: number
  /** Rest between two sets (0: none). Never after the last set. */
  setRest: number
  /** A last easy section once the work is done (0: none). */
  coolDown: number
}

export type SettingName = keyof HiitSettings

/** The Tabata Timer app's own defaults: one Tabata of 8 × 20 s on / 10 s off. */
export const DEFAULTS: HiitSettings = {
  prepare: 10,
  work: 20,
  rest: 10,
  cycles: 8,
  sets: 1,
  setRest: 60,
  coolDown: 0,
}

/** The order the settings are shown in. */
export const SETTING_NAMES: SettingName[] = [
  'prepare',
  'work',
  'rest',
  'cycles',
  'sets',
  'setRest',
  'coolDown',
]

/** What each setting may be, and how much one tap of − or + changes it. */
export const LIMITS: Record<SettingName, { min: number; max: number; step: number }> = {
  prepare: { min: 0, max: 300, step: 5 },
  work: { min: 1, max: 900, step: 5 },
  rest: { min: 0, max: 900, step: 5 },
  cycles: { min: 1, max: 50, step: 1 },
  sets: { min: 1, max: 20, step: 1 },
  setRest: { min: 0, max: 900, step: 15 },
  coolDown: { min: 0, max: 1800, step: 30 },
}

export type Phase = 'prepare' | 'work' | 'rest' | 'setRest' | 'coolDown'
export type Section = { phase: Phase; cycle: number; set: number; start: number; end: number }

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)))
}

/** A setting from what the user typed: a number inside its limits, else the fallback. */
export function parseSetting(name: SettingName, text: string, fallback: number): number {
  const value = Number(text)
  const { min, max } = LIMITS[name]
  return text.trim() === '' || !Number.isFinite(value) ? fallback : clamp(value, min, max)
}

/** What the user has typed in each field, before it is checked. */
export type Draft = Record<SettingName, string>

export function toDraft(settings: HiitSettings): Draft {
  return Object.fromEntries(SETTING_NAMES.map((n) => [n, String(settings[n])])) as Draft
}

export function fromDraft(draft: Draft, fallback: HiitSettings): HiitSettings {
  return Object.fromEntries(
    SETTING_NAMES.map((n) => [n, parseSetting(n, draft[n], fallback[n])]),
  ) as HiitSettings
}

/** Settings from anything (stored JSON, props): each field inside its limits, else the default. */
export function sanitize(value: unknown): HiitSettings {
  const source = (typeof value === 'object' && value !== null ? value : {}) as Record<
    string,
    unknown
  >
  const out = { ...DEFAULTS }
  for (const name of SETTING_NAMES) {
    const v = source[name]
    if (typeof v === 'number' && Number.isFinite(v)) {
      out[name] = clamp(v, LIMITS[name].min, LIMITS[name].max)
    }
  }
  return out
}

/**
 * Prepare, then each set's cycles of work and rest, rest between sets, then cool down. A set's
 * last cycle has no rest of its own: the rest between sets (or the end) follows it instead.
 * Sections of 0 seconds are left out.
 */
export function buildSchedule(s: HiitSettings): Section[] {
  const sections: Section[] = []
  let t = 0
  const add = (phase: Phase, seconds: number, cycle: number, set: number) => {
    if (seconds <= 0) return
    sections.push({ phase, cycle, set, start: t, end: t + seconds })
    t += seconds
  }
  add('prepare', s.prepare, 1, 1)
  for (let set = 1; set <= s.sets; set++) {
    for (let cycle = 1; cycle <= s.cycles; cycle++) {
      add('work', s.work, cycle, set)
      if (cycle < s.cycles) add('rest', s.rest, cycle, set)
    }
    if (set < s.sets) add('setRest', s.setRest, s.cycles, set)
  }
  add('coolDown', s.coolDown, s.cycles, s.sets)
  return sections
}

/** The whole run in seconds, prepare and cool down included. */
export function totalSeconds(schedule: Section[]): number {
  return schedule.length ? schedule[schedule.length - 1].end : 0
}

export type Position = { index: number; section: Section; remaining: number; done: boolean }

/** Where the workout is after `elapsed` seconds: the section, and the seconds left in it. */
export function positionAt(schedule: Section[], elapsed: number): Position {
  const index = schedule.findIndex((s) => elapsed < s.end)
  if (index === -1) {
    return {
      index: schedule.length,
      section: schedule[schedule.length - 1],
      remaining: 0,
      done: true,
    }
  }
  const section = schedule[index]
  return { index, section, remaining: section.end - elapsed, done: false }
}

/** Within this many seconds of a section's start, Back goes to the section before. */
export const BACK_GRACE = 2

/**
 * The elapsed time after a skip. Forward jumps to the next section (or the end); back restarts
 * the current section, or goes to the one before when it has only just started.
 */
export function skip(schedule: Section[], elapsed: number, direction: 'back' | 'forward'): number {
  const at = positionAt(schedule, elapsed)
  if (direction === 'forward') return at.done ? elapsed : at.section.end
  const index = Math.min(at.index, schedule.length - 1)
  const section = schedule[index]
  if (elapsed - section.start >= BACK_GRACE || index === 0) return section.start
  return schedule[index - 1].start
}

/** A round counts once its work section has ended, unless it was skipped. */
export function roundsCompleted(
  schedule: Section[],
  elapsed: number,
  skipped: ReadonlySet<number> = new Set(),
): number {
  return schedule.filter((s, i) => s.phase === 'work' && s.end <= elapsed && !skipped.has(i)).length
}

/** The seconds of workout done: the time line so far, without the prepare count. */
export function activeSeconds(schedule: Section[], elapsed: number): number {
  const t = Math.min(Math.max(0, elapsed), totalSeconds(schedule))
  const prepare = schedule[0]?.phase === 'prepare' ? schedule[0].end : 0
  return Math.max(0, Math.round(t - prepare))
}

export type Cue = 'Work' | 'Rest' | 'Halfway' | 'Last round' | 'Cool down'

/** What the voice says as section `index` starts, if anything. */
export function cueFor(schedule: Section[], index: number): Cue | null {
  const section = schedule[index]
  if (!section) return null
  if (section.phase === 'rest' || section.phase === 'setRest') return 'Rest'
  if (section.phase === 'coolDown') return 'Cool down'
  if (section.phase !== 'work') return null
  const works = schedule.filter((s) => s.phase === 'work')
  const number = schedule.slice(0, index + 1).filter((s) => s.phase === 'work').length
  if (number === works.length && works.length > 1) return 'Last round'
  if (works.length >= 4 && number === Math.floor(works.length / 2) + 1) return 'Halfway'
  return 'Work'
}

/** 230 -> "3:50", 3725 -> "1:02:05". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** The big clock: plain seconds under a minute, m:ss above. */
export function formatClock(remaining: number): string {
  const s = Math.max(0, Math.ceil(remaining))
  return s < 60 ? String(s) : formatDuration(s)
}
