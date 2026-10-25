import { useState } from 'react'
import { fetchStretching, logStretching, SignedOutError, type Routine } from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { card } from '../ui'
import StretchPlayer from './StretchPlayer'

const CHOICES = [10, 20, 30] // minutes, as the bot offers (ADR-0032)

const choice =
  'min-h-11 flex-1 rounded-xl border-2 border-[var(--ink)] px-4 font-bold text-[var(--ink)] disabled:opacity-60'

type State =
  | { status: 'choose' }
  | { status: 'routine'; routine: Routine }
  | { status: 'done'; minutes: number; logged: boolean }
  | { status: 'discarded' }

/** After a saved resistance session: pick a time, see what's coming, then follow the bells
 * (or stretch without the phone) and log the minutes (#135, ADR-0032 addendum). */
export default function Stretching({ workoutId }: { workoutId: number }) {
  const [state, setState] = useState<State>({ status: 'choose' })
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)

  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setNote(null)
    setSignedOut(false) // a retry after signing in again
    try {
      await work()
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't reach the coach. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const choose = (minutes: number) =>
    run(async () => {
      const routine = await fetchStretching(workoutId, minutes)
      if (routine === null) setNote('No stretching for this workout.')
      else setState({ status: 'routine', routine })
    })

  const done = (minutes: number) =>
    run(async () => {
      setState({ status: 'done', minutes, logged: await logStretching(workoutId, minutes) })
    })

  return (
    <section aria-labelledby="stretching" className={card + ' flex flex-col gap-3'}>
      <h2 id="stretching" className="text-lg font-bold">
        Stretching
      </h2>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}

      {state.status === 'choose' && (
        <>
          <p className="text-[var(--slate)]">For the muscles you just worked. How long?</p>
          <div className="flex gap-3">
            {CHOICES.map((minutes) => (
              <button
                key={minutes}
                type="button"
                className={choice}
                disabled={busy}
                onClick={() => choose(minutes)}
              >
                {minutes} min
              </button>
            ))}
          </div>
        </>
      )}

      {state.status === 'routine' && (
        <StretchPlayer
          routine={state.routine}
          busy={busy}
          onLog={done}
          onDiscard={() => setState({ status: 'discarded' })}
        />
      )}

      {state.status === 'done' && (
        <p>
          {state.logged
            ? `Logged ${state.minutes} min of stretching.`
            : 'Stretching was already logged for this session.'}
        </p>
      )}

      {state.status === 'discarded' && <p>Not logged.</p>}
    </section>
  )
}
