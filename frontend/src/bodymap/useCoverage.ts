import { useEffect, useState } from 'react'
import { fetchCoverage, type Coverage } from '../api'

export type State =
  | { status: 'loading' }
  | { status: 'hidden' }
  | { status: 'error'; message: string }
  | { status: 'ready'; coverage: Coverage }

/** The coverage for the Plan page: fetched once, shared by the week's map and each session's. */
export function useCoverage(): State {
  const [state, setState] = useState<State>({ status: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    fetchCoverage(ctrl.signal)
      .then((coverage) => setState(coverage ? { status: 'ready', coverage } : { status: 'hidden' }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => ctrl.abort()
  }, [])
  return state
}
