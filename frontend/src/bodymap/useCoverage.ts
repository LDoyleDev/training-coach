import { useEffect, useState } from 'react'
import { fetchCoverage, type Coverage, type Place } from '../api'

export type State =
  | { status: 'loading' }
  | { status: 'hidden' }
  | { status: 'error'; message: string }
  | { status: 'ready'; coverage: Coverage }

/** The coverage for the Plan page, shared by the week's map and each session's: fetched once,
 * and again when the person picks Home or Gym (``place``; unset: the day's place). The maps
 * keep the last answer while the next one loads. */
export function useCoverage(place?: Place): State {
  const [state, setState] = useState<State>({ status: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    fetchCoverage(place, ctrl.signal)
      .then((coverage) => setState(coverage ? { status: 'ready', coverage } : { status: 'hidden' }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => ctrl.abort()
  }, [place])
  return state
}
