import { useEffect, useState } from 'react'
import { fetchPlan, type Plan } from './api'
import { ChatPreview } from './components/ChatPreview'
import { CycleRing } from './components/CycleRing'
import { Ladders } from './components/Ladders'
import { SessionList } from './components/SessionList'
import { VolumeChart } from './components/VolumeChart'

const LADDER_PICKS = [
  'pull-up',
  'push-up',
  'bulgarian-split-squat',
  'pistol-squat',
  'hamstring-curl',
]

type State =
  { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; plan: Plan }

export default function App() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchPlan(ctrl.signal)
      .then((plan) => setState({ status: 'ready', plan }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => ctrl.abort()
  }, [])

  const toggle = (slug: string) => setOpen((cur) => (cur === slug ? null : slug))
  const selectFromRing = (slug: string) => {
    setOpen(slug)
    document.getElementById(`row-${slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>

      {state.status === 'loading' && <p className="status">Loading the plan…</p>}
      {state.status === 'error' && (
        <p className="status status-error" role="alert">
          Couldn't load the plan. {state.message} Check that the server is running, then reload the
          page.
        </p>
      )}

      {state.status === 'ready' && (
        <main>
          <section className="hero">
            <div className="hero-text">
              <h1>Seven sessions, one fixed order</h1>
              <p className="lede">
                Strength, conditioning and recovery from Huberman's foundational fitness protocol,
                adapted for training at home with a pull-up bar, two chairs and an 8 kg kettlebell.
              </p>
              <p className="lede">
                Miss a day and the whole week moves back one day. Nothing gets skipped.
              </p>
              <ul className="legend">
                <li className="legend-strength">Strength</li>
                <li className="legend-conditioning">Conditioning</li>
                <li className="legend-recovery">Recovery</li>
              </ul>
            </div>
            <CycleRing sessions={state.plan.sessions} selected={open} onSelect={selectFromRing} />
          </section>

          <section className="block" aria-labelledby="week">
            <h2 id="week">The week</h2>
            <p className="block-intro">Open a session to see its exercises and targets.</p>
            <SessionList sessions={state.plan.sessions} open={open} onToggle={toggle} />
          </section>

          <section className="block" aria-labelledby="volume">
            <h2 id="volume">Hard sets per muscle, per week</h2>
            <p className="block-intro">
              Every set counts for each muscle an exercise works, so these are upper estimates.
            </p>
            <VolumeChart
              volume={state.plan.volume}
              min={state.plan.volume_target_min}
              max={state.plan.volume_target_max}
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

          <section className="block block-split" aria-labelledby="day">
            <div>
              <h2 id="day">A day with the coach</h2>
              <p className="block-intro">
                Everything happens in Telegram. The day's session arrives at 07:30, the workout is
                logged with one voice note, and nothing is saved until it's confirmed.
              </p>
              <p className="aside">Planned flow. The Telegram bot is being built now.</p>
            </div>
            <ChatPreview />
          </section>
        </main>
      )}

      <footer className="footer">
        <p>
          Built by Liam Doyle with Claude Code. Runs on a Raspberry Pi at home. Programme based on
          Huberman Lab episode 94, with Andy Galpin.
        </p>
      </footer>
    </div>
  )
}
