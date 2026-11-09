import { useEffect, useState } from 'react'
import { fetchPlan, type Place, type Plan, type Session } from './api'
import { BodyMap } from './bodymap/BodyMap'
import { MapPlace } from './bodymap/MapPlace'
import { useCoverage } from './bodymap/useCoverage'
import { CycleRing } from './components/CycleRing'
import { Ladders } from './components/Ladders'
import { SessionList } from './components/SessionList'
import { card, primaryInline } from './ui'

const LADDER_PICKS = [
  'pull-up',
  'push-up',
  'bulgarian-split-squat',
  'pistol-squat',
  'hamstring-curl',
]

const NUMBERS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
const KINDS: [Session['type'], string][] = [
  ['strength', 'Strength'],
  ['conditioning', 'conditioning'],
  ['recovery', 'recovery'],
]

/** The hero's words from the person's plan (ADR-0092, Decided 20): how many sessions, and of
 * which kinds, in the legend's order. */
function hero(plan: Plan) {
  const n = plan.sessions.length
  const kinds = KINDS.filter(([kind]) => plan.sessions.some((s) => s.type === kind))
  const names = kinds.map(([, name], i) => (i === 0 ? name[0].toUpperCase() + name.slice(1) : name))
  const list =
    names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
  return {
    title: `${NUMBERS[n] ?? n} ${n === 1 ? 'session' : 'sessions'}, one fixed order`,
    lede: `${list}: each exercise at the step you're on, moving up as you go.`,
    kinds: kinds.map(([kind]) => kind),
  }
}

type State =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error'; message: string }
  | { status: 'ready'; plan: Plan }

/** The plan: the cycle, each session with what it works (its own body map, ADR-0069), the
 * ladders, and at the bottom what the whole week gives each muscle. The maps and each session's
 * exercises are the home or gym versions: the day's place, with Home | Gym for someone who trains
 * at both (ADR-0071). Its page gives it the frame. */
export default function App() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [open, setOpen] = useState<string | null>(null)
  const [asked, setAsked] = useState<{ place: Place }>()
  const coverage = useCoverage(asked)
  const counted = coverage.status === 'ready' ? coverage.coverage : undefined
  const choice = counted?.places === 'both' && (
    <MapPlace
      place={counted.place}
      problem={coverage.status === 'ready' ? coverage.problem : undefined}
      onChoose={(place) => place !== counted.place && setAsked({ place })}
    />
  )

  useEffect(() => {
    const ctrl = new AbortController()
    fetchPlan(ctrl.signal)
      .then((plan) => setState(plan ? { status: 'ready', plan } : { status: 'signed-out' }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => ctrl.abort()
  }, [])

  const words = state.status === 'ready' ? hero(state.plan) : null
  const toggle = (slug: string) => setOpen((cur) => (cur === slug ? null : slug))
  const selectFromRing = (slug: string) => {
    setOpen(slug)
    document.getElementById(`row-${slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  return (
    <>
      {state.status === 'loading' && <p className="status">Loading the plan…</p>}
      {state.status === 'signed-out' && (
        <div className={card}>
          <p className="m-0 mb-3">Sign in to see your plan.</p>
          <a
            href="/signin?next=/plan"
            className={`${primaryInline} inline-flex items-center no-underline`}
          >
            Sign in
          </a>
        </div>
      )}
      {state.status === 'error' && (
        <p className="status status-error" role="alert">
          Couldn't load the plan. {state.message} Check your connection, then try again.{' '}
          <button type="button" onClick={() => window.location.reload()}>
            Try again
          </button>
        </p>
      )}

      {state.status === 'ready' && words && (
        <div>
          <section className="hero">
            <div className="hero-text">
              <h2>{words.title}</h2>
              <p className="lede">{words.lede}</p>
              <p className="lede">
                Miss a day and the next session waits for you. Nothing gets skipped.
              </p>
              <ul className="legend" aria-label="Kinds of session">
                {words.kinds.map((kind) => (
                  <li key={kind} className={`legend-${kind}`}>
                    {kind[0].toUpperCase() + kind.slice(1)}
                  </li>
                ))}
              </ul>
            </div>
            <CycleRing sessions={state.plan.sessions} selected={open} onSelect={selectFromRing} />
          </section>

          <section className="block" aria-labelledby="week">
            <h2 id="week">The week</h2>
            <p className="block-intro">
              Open a session to see what it works, its exercises and targets.
            </p>
            {choice}
            <SessionList
              sessions={state.plan.sessions}
              open={open}
              onToggle={toggle}
              coverage={counted}
            />
          </section>

          <section className="block" aria-labelledby="ladders">
            <h2 id="ladders">Harder without heavier weights</h2>
            <p className="block-intro">
              Each exercise has a ladder of harder variations. Hit the top of the rep range in two
              sessions running and the coach suggests the next step.
            </p>
            <Ladders
              exercises={LADDER_PICKS.flatMap((slug) => {
                const ex = state.plan.sessions
                  .flatMap((s) => s.exercises)
                  .find((e) => e.slug === slug)
                return ex ? [ex] : []
              })}
            />
          </section>

          <section className="block" aria-labelledby="volume">
            <h2 id="volume">What the week gives each muscle</h2>
            <p className="block-intro">
              The whole week{counted?.place === 'gym' && ' at the gym'}: hard sets per muscle,
              coloured by how close each is to its target.
            </p>
            {choice}
            <BodyMap state={coverage} />
          </section>
        </div>
      )}

      <footer className="footer">
        <p>
          Training principles informed by publicly available material, including Huberman Lab
          episode 94 with Andy Galpin. Not affiliated with or endorsed by Huberman Lab, Andrew
          Huberman or Andy Galpin.
        </p>
      </footer>
    </>
  )
}
