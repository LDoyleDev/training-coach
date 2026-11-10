import type { Band, Coverage, Heat, ItemMuscle, MuscleCoverage } from '../api'

/** The six bands as people read them (program-builder.md, Decided 3). */
export const BANDS: readonly { band: Band; label: string; means: string }[] = [
  { band: 'grey', label: 'Not trained', means: '0 sets' },
  { band: 'amber', label: 'Below the minimum', means: 'under 4 sets' },
  { band: 'light green', label: 'Minimum', means: 'enough to maintain' },
  { band: 'green', label: 'On target', means: 'the green band, on two days' },
  { band: 'blue', label: 'High', means: 'diminishing returns' },
  { band: 'warning', label: 'Too much', means: 'over 30 sets' },
]

/** One session's map: how hard it works each muscle (ADR-0069). Not the week's bands. */
export const HEATS: readonly { heat: Heat; label: string }[] = [
  { heat: 'none', label: 'Not worked' },
  { heat: 'light', label: 'A little' },
  { heat: 'worked', label: 'Worked' },
  { heat: 'hard', label: 'Worked hard' },
  { heat: 'over', label: 'Too much for one session' },
]

export const heatLabel = (heat: Heat) => HEATS.find((h) => h.heat === heat)?.label ?? heat

export const bandLabel = (band: Band) => BANDS.find((b) => b.band === band)?.label ?? band

export const muscleName = (m: string) => m.charAt(0).toUpperCase() + m.slice(1)

/** 7.5, 10, 7.25: fractional sets without a needless decimal. */
export const sets = (n: number) => `${Math.round(n * 100) / 100}`

const plural = (n: number, one: string, many: string) => `${sets(n)} ${n === 1 ? one : many}`

const WEEK = 7

/** Over a week, or over the cycle's own days when it isn't 7 (ADR-0093 Decided 15). */
export const per = (cycleDays: number) =>
  cycleDays === WEEK ? 'a week' : `per ${cycleDays}-day cycle`

/** The days green needs in a cycle: two per 7 days, rounded half up and never under one, as
 * `domain.coverage.days_needed`: 2 in an 8-day cycle, 3 in a 10-day one. */
export const daysNeeded = (cycleDays: number) =>
  Math.max(1, Math.floor((4 * cycleDays + WEEK) / (2 * WEEK)))

/** A weekly number stretched to the cycle, to one decimal: 10 a week is 11.4 per 8 days. */
const stretched = (weekly: number, cycleDays: number) =>
  Math.round((weekly * cycleDays * 10) / WEEK) / 10

/** "Sets per 8-day cycle." when the cycle isn't 7 days; null when it is. */
export const cycleLine = (c: Coverage) =>
  c.cycle_days === WEEK ? null : `Sets per ${c.cycle_days}-day cycle.`

/** "Counted at your 30 minutes and 5 exercises a session." when the map counted the plan at the
 * person's settings (Decided 16); null when it counted it as planned. */
export function countedLine(c: Coverage): string | null {
  const minutes = c.session_minutes === null ? null : `${c.session_minutes} minutes`
  const count =
    c.session_exercises === null ? null : plural(c.session_exercises, 'exercise', 'exercises')
  const what = [minutes, count].filter(Boolean).join(' and ')
  return what ? `Counted at your ${what} a session.` : null
}

/** "8.5 sets a week on 1 day", "8.5 sets per 8-day cycle on 1 day" */
export function amount(m: MuscleCoverage, cycleDays = WEEK): string {
  if (m.sets === 0)
    return cycleDays === WEEK ? 'Not trained this week' : 'Not trained in your cycle'
  return `${plural(m.sets, 'set', 'sets')} ${per(cycleDays)} on ${plural(m.days, 'day', 'days')}`
}

/** "Green: 10–20 sets on two days"; over an 8-day cycle "Green: 11.4–22.9 sets on 2 days" */
export function goal(m: MuscleCoverage, cycleDays = WEEK): string {
  const both = m.main || m.evidence === null
  if (cycleDays === WEEK)
    return `Green: ${sets(m.low)}–${sets(m.high)} sets${both ? ' on two days' : ''}`
  const days = both ? ` on ${plural(daysNeeded(cycleDays), 'day', 'days')}` : ''
  // The band comes stretched to the cycle already (Decided 15): to one decimal.
  const one = (n: number) => sets(Math.round(n * 10) / 10)
  return `Green: ${one(m.low)}–${one(m.high)} sets${days}`
}

const PARTS: Record<string, string> = {
  'triceps long head': 'Nothing reaches the triceps long head: it needs an overhead extension.',
  'rectus femoris':
    'Nothing reaches the rectus femoris (front of the thigh): it needs a leg extension.',
}

/** The warnings on one muscle, in the order they matter. */
export function warnings(m: MuscleCoverage, c: Coverage): string[] {
  const found: string[] = []
  const d = c.cycle_days
  const ceiling = d === WEEK ? c.ceiling : stretched(c.ceiling, d)
  if (m.band === 'warning')
    found.push(`Over ${sets(ceiling)} sets ${per(d)}: more showed no extra growth.`)
  if (m.over_session_cap && m.most_in)
    found.push(
      `${sets(m.most)} sets in ${m.most_in}: more than ${c.session_cap} in one session adds little.`,
    )
  if (m.one_day && d === WEEK)
    found.push(
      m.band === 'light green' && m.sets >= m.low
        ? 'Enough sets, but on one day: green needs two days a week.'
        : 'Trained on one day a week: green needs two.',
    )
  else if (m.one_day) {
    const on = m.days === 1 ? 'only one day' : plural(m.days, 'day', 'days')
    const need = daysNeeded(d)
    found.push(
      m.band === 'light green' && m.sets >= m.low
        ? `Enough sets, but on ${on}: green needs ${need} days of your cycle.`
        : `Trained on ${on} of your cycle: green needs ${need}.`,
    )
  }
  const [a, b] = m.back_to_back
  if (a && b)
    found.push(
      `${c.back_to_back}+ sets in ${a} and again in ${b}, two days running: little rest between. A rule of thumb, not a study.`,
    )
  for (const part of m.missing_parts) found.push(PARTS[part] ?? `Nothing reaches the ${part}.`)
  return found
}

/** The week's warnings beyond any one muscle: a session over an hour or past the rule-of-thumb caps
 * on the spine or grip, and pushing without pulling. */
export function sessionWarnings(c: Coverage): string[] {
  const week = c.pushing_without_pulling
    ? [
        `${c.push_sets} pushing sets ${per(c.cycle_days)} and ${c.pull_sets} pulling: a rule of thumb is at least one pulling set for two pushing.`,
      ]
    : []
  const sessions = c.sessions.flatMap((s) => [
    ...(s.over_an_hour ? [`${s.session}: about ${s.minutes} minutes, over an hour.`] : []),
    ...(s.spine_heavy
      ? [`${s.session}: ${s.spine_sets} spine-loading sets, over ${c.spine_cap} in one session.`]
      : []),
    ...(s.grip_heavy
      ? [
          `${s.session}: ${s.grip_sets} grip-heavy sets, over ${c.grip_cap}: straps or a grip-free option help.`,
        ]
      : []),
  ])
  return [...sessions, ...week]
}

/** How hard one exercise works a muscle, on the session map's colours: the main mover (1) worked
 * hard, a helper (½) worked, a small part (¼) a little. */
export const weightHeat = (weight: number): Heat =>
  weight >= 1 ? 'hard' : weight >= 0.5 ? 'worked' : 'light'

/** "Works: Lats · helped by biceps, upper back · a little: rear delts, forearms", for the set
 * screen; "" for an exercise that works no muscle (cardio, mobility). */
export function worksLine(muscles: readonly ItemMuscle[], parts: readonly string[] = []): string {
  const groups = (['hard', 'worked', 'light'] as const)
    .map((heat) => muscles.filter((m) => weightHeat(m.weight) === heat).map((m) => m.muscle))
    .map((names, i) => ({ names, label: ['', 'helped by ', 'a little: '][i] }))
    .filter((g) => g.names.length > 0)
  if (groups.length === 0) return ''
  const said = groups.map((g, i) =>
    i === 0 ? `Works: ${muscleName(g.names.join(', '))}` : g.label + g.names.join(', '),
  )
  return [...said, ...parts.map((p) => `reaches the ${p}`)].join(' · ')
}
