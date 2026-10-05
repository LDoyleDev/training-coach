export type ExerciseKind = 'reps' | 'seconds' | 'duration_min'
export type SessionType = 'strength' | 'conditioning' | 'recovery'

export type Exercise = {
  slug: string
  name: string
  kind: ExerciseKind
  sets: number
  rep_min: number
  rep_max: number
  per_side: boolean
  muscle_groups: string[]
  ladder: string[]
  current_step: number
}

export type Session = {
  position: number
  slug: string
  name: string
  focus: string
  type: SessionType
  optional: boolean
  total_sets: number
  exercises: Exercise[]
}

export type Plan = {
  sessions: Session[]
  volume: { group: string; sets: number }[]
  volume_target_min: number
  volume_target_max: number
}

export async function fetchPlan(signal?: AbortSignal): Promise<Plan> {
  const res = await fetch('/api/plan', { signal })
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Plan
}

const range = (a: number, b: number) => (a === b ? `${a}` : `${a}–${b}`)

/** "4 × 8–15 per side", "1 × 45–75 min", "2 × 30–60 s" */
export function prescription(e: Exercise): string {
  const unit = e.kind === 'duration_min' ? ' min' : e.kind === 'seconds' ? ' s' : ''
  const side = e.per_side ? ' per side' : ''
  const body = `${range(e.rep_min, e.rep_max)}${unit}${side}`
  return e.sets === 1 ? body : `${e.sets} × ${body}`
}

/** Short headline figure for a session: sets for strength work, minutes for cardio. */
export function sessionSize(s: Session): string {
  const timed = s.exercises.find((e) => e.kind === 'duration_min')
  if (s.type === 'conditioning' && timed) return `${range(timed.rep_min, timed.rep_max)} min`
  if (s.type === 'conditioning') return `${s.exercises[0]?.rep_min ?? 0}+ rounds`
  return `${s.total_sets} sets`
}
