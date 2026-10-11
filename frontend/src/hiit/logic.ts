/** The HIIT timer's schedule, as pure functions of the settings and the elapsed time. */

export type HiitSettings = { rounds: number; work: number; rest: number }

export const DEFAULTS: HiitSettings = { rounds: 8, work: 20, rest: 10 }

/** What each setting may be, and how much one tap of − or + changes it. */
export const LIMITS: Record<keyof HiitSettings, { min: number; max: number; step: number }> = {
  rounds: { min: 1, max: 30, step: 1 },
  work: { min: 5, max: 300, step: 5 },
  rest: { min: 0, max: 300, step: 5 },
}

/** The "Get ready" count before round 1, in seconds. */
export const LEAD_IN = 3

export type Phase = 'ready' | 'work' | 'rest'
export type Section = { phase: Phase; round: number; start: number; end: number }

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)))
}

/** A setting from what the user typed: a number inside its limits, else the fallback. */
export function parseSetting(name: keyof HiitSettings, text: string, fallback: number): number {
  const value = Number(text)
  const { min, max } = LIMITS[name]
  return text.trim() === '' || !Number.isFinite(value) ? fallback : clamp(value, min, max)
}

/** Lead-in, then work and rest in turn. No rest after the last round, none at all when rest is 0. */
export function buildSchedule({ rounds, work, rest }: HiitSettings): Section[] {
  const sections: Section[] = [{ phase: 'ready', round: 1, start: 0, end: LEAD_IN }]
  let t = LEAD_IN
  for (let round = 1; round <= rounds; round++) {
    sections.push({ phase: 'work', round, start: t, end: t + work })
    t += work
    if (rest > 0 && round < rounds) {
      sections.push({ phase: 'rest', round, start: t, end: t + rest })
      t += rest
    }
  }
  return sections
}

/** The workout itself in seconds, without the lead-in. */
export function workoutSeconds({ rounds, work, rest }: HiitSettings): number {
  return rounds * work + (rounds - 1) * rest
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

/** A round counts once its work section has ended. */
export function roundsCompleted(schedule: Section[], elapsed: number): number {
  return schedule.filter((s) => s.phase === 'work' && s.end <= elapsed).length
}

/** 230 -> "3:50". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** The big clock: plain seconds under a minute, m:ss above. */
export function formatClock(remaining: number): string {
  const s = Math.max(0, Math.ceil(remaining))
  return s < 60 ? String(s) : formatDuration(s)
}
