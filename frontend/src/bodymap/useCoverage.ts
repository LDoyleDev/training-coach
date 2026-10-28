import { useEffect, useState } from 'react'
import { fetchCoverage, type Coverage, type Place } from '../api'

export type State =
  | { status: 'loading' }
  | { status: 'hidden' }
  | { status: 'error'; message: string }
  // ``problem``: the next answer (Home or Gym) failed, so the maps still show this one
  | { status: 'ready'; coverage: Coverage; problem?: string }

/** The coverage for the Plan page, shared by the week's map and each session's: fetched once,
 * and again for each Home or Gym the person picks (``asked``, a new object each time, so asking
 * again after a failure tries again; unset: the day's place). The maps keep the last answer
 * while the next one loads, and when it fails. */
export function useCoverage(asked?: { place: Place }): State {
  const [state, setState] = useState<State>({ status: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    fetchCoverage(asked?.place, ctrl.signal)
      .then((coverage) => setState(coverage ? { status: 'ready', coverage } : { status: 'hidden' }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        const message = err instanceof Error ? err.message : String(err)
        setState((cur) =>
          cur.status === 'ready' ? { ...cur, problem: message } : { status: 'error', message },
        )
      })
    return () => ctrl.abort()
  }, [asked])
  return state
}
