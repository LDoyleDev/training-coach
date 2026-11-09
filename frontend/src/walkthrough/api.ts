/**
 * GET /api/walkthrough's ladders (ADR-0092, API). A STUB until that route's generated types
 * exist (#678): the shape is the ADR's outline, and only the part screen 9 reads. Swap these for
 * `Schemas[...]` from `../api` once the route lands; nothing else here changes.
 */

/** One ladder step, easiest first: the bottom one has no question, as everyone starts there. */
export interface WalkStep {
  id: number
  name: string // its figure is drawn from the exercise and this name
  level: number
  question: string | null
  cue: string | null
  needs: string[] // the catalogue's, as `domain.kit` reads them: "kettlebell:16"
  marks: string[] // "floor", "kneeling", ...
}

export interface WalkLadder {
  slug: string
  name: string
  steps: WalkStep[]
}

export interface Walkthrough {
  ladders: WalkLadder[]
}

/** The ladders to walk; null when signed out. */
export async function fetchWalkthrough(signal?: AbortSignal): Promise<Walkthrough | null> {
  const res = await fetch('/api/walkthrough', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Walkthrough
}
