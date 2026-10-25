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

/** "8.5 sets a week on 1 day" */
export function amount(m: MuscleCoverage): string {
  if (m.sets === 0) return 'Not trained this week'
  return `${plural(m.sets, 'set', 'sets')} a week on ${plural(m.days, 'day', 'days')}`
}

/** "Green: 10–20 sets on two days" */
export function goal(m: MuscleCoverage): string {
  const days = m.main || m.evidence === null ? ' on two days' : ''
  return `Green: ${sets(m.low)}–${sets(m.high)} sets${days}`
}

const PARTS: Record<string, string> = {
  'triceps long head': 'Nothing reaches the triceps long head: it needs an overhead extension.',
  'rectus femoris':
    'Nothing reaches the rectus femoris (front of the thigh): it needs a leg extension.',
}

/** The warnings on one muscle, in the order they matter. */
export function warnings(m: MuscleCoverage, c: Coverage): string[] {
  const found: string[] = []
  if (m.band === 'warning')
    found.push(`Over ${c.ceiling} sets a week: more showed no extra growth.`)
  if (m.over_session_cap && m.most_in)
    found.push(
      `${sets(m.most)} sets in ${m.most_in}: more than ${c.session_cap} in one session adds little.`,
    )
  if (m.one_day)
    found.push(
      m.band === 'light green' && m.sets >= m.low
        ? 'Enough sets, but on one day: green needs two days a week.'
        : 'Trained on one day a week: green needs two.',
    )
  const [a, b] = m.back_to_back
  if (a && b)
    found.push(
      `${c.back_to_back}+ sets in ${a} and again in ${b}, two days running: little rest between. A rule of thumb, not a study.`,
    )
  for (const part of m.missing_parts) found.push(PARTS[part] ?? `Nothing reaches the ${part}.`)
  return found
}

/** The sessions that load the spine or grip past the rule-of-thumb caps. */
export function sessionWarnings(c: Coverage): string[] {
  return c.sessions.flatMap((s) => [
    ...(s.spine_heavy
      ? [`${s.session}: ${s.spine_sets} spine-loading sets, over ${c.spine_cap} in one session.`]
      : []),
    ...(s.grip_heavy
      ? [
          `${s.session}: ${s.grip_sets} grip-heavy sets, over ${c.grip_cap}: straps or a grip-free option help.`,
        ]
      : []),
  ])
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
