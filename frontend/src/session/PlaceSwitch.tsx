import { useState } from 'react'
import { choosePlace, type Guided, type Place, SignedOutError, type TodayView } from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { actions, card, primaryInline, secondary } from '../ui'

const NAMES: Record<Place, string> = { home: 'Home', gym: 'Gym', away: 'Away' }
const AT: Record<Place, string> = {
  home: 'at home',
  gym: 'at the gym',
  away: 'away, with no equipment',
}
const VERSION: Record<Place, string> = {
  home: 'home version',
  gym: 'gym version',
  away: 'no-equipment version',
}
const SAYS: Record<Place, string> = {
  home: 'The home version, with your own kit.',
  gym: 'The gym version, with weights that carry over from last time.',
  away:
    'Away, no equipment: bodyweight, a chair, a bed, a wall, a towel. A step that needs kit is ' +
    'done at the highest one below it that doesn’t, for today only; your levels stay.',
}
const COLUMNS: Record<number, string> = { 2: 'grid-cols-2', 3: 'grid-cols-3' }

const option = (on: boolean) =>
  'min-h-11 w-full rounded-xl border-2 px-4 font-bold disabled:opacity-60 ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/**
 * Today's Home | Gym | Away switch (ADR-0071, ADR-0086): Home | Gym when the session has a gym
 * version and the person trains at both, and Away, with no equipment, when it has an away
 * version, for anyone; the server says which (`places`). It starts at the last place chosen
 * (Away is for the day only); a tap changes the day's exercises before anything is kept. With
 * sets kept it asks first, as a clash does (ADR-0060): switching drops them. The app never
 * switches by itself.
 */
export default function PlaceSwitch({
  session,
  onChanged,
  onStale,
}: {
  session: Guided
  onChanged: (today: TodayView, text: string) => void
  onStale: () => void
}) {
  const [asking, setAsking] = useState<{ place: Place; sets: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  // The server always lists them; the API types make a field with a default optional.
  const places = session.places ?? (['home', 'gym'] as const)

  const choose = async (place: Place, confirm = false) => {
    if (place === session.place && !confirm) return
    setBusy(true)
    setProblem(null)
    setSignedOut(false)
    try {
      const result = await choosePlace(place, confirm)
      if (result === 'stale') return onStale()
      if ('ask' in result) return setAsking({ place, sets: result.ask })
      setAsking(null)
      onChanged(result, `${session.name} ${AT[place]}: its ${VERSION[place]}.`)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setProblem("That didn't work. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="place" className={card + ' flex flex-col gap-3'}>
      <h2 id="place" className="m-0 text-lg font-bold">
        Where are you training today?
      </h2>
      <div
        role="group"
        aria-labelledby="place"
        className={`grid ${COLUMNS[places.length] ?? 'grid-cols-2'} gap-2`}
      >
        {places.map((place) => (
          <button
            key={place}
            type="button"
            aria-pressed={session.place === place}
            className={option(session.place === place)}
            disabled={busy}
            onClick={() => choose(place)}
          >
            {session.place === place && <span aria-hidden="true">✓ </span>}
            {NAMES[place]}
          </button>
        ))}
      </div>
      <p className="m-0 text-sm text-[var(--slate)]">{SAYS[session.place]}</p>
      {asking && (
        <div role="alertdialog" aria-labelledby="place-ask" className="flex flex-col gap-2">
          <p id="place-ask" className="m-0 font-bold">
            You've kept {asking.sets} {asking.sets === 1 ? 'set' : 'sets'} of the{' '}
            {VERSION[session.place]}. Switch to the {VERSION[asking.place]}?{' '}
            {asking.sets === 1 ? 'It is' : 'They are'} dropped; nothing saved changes.
          </p>
          <div className={actions}>
            <button
              type="button"
              className={primaryInline}
              disabled={busy}
              onClick={() => choose(asking.place, true)}
            >
              Switch to {NAMES[asking.place].toLowerCase()}
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy}
              onClick={() => setAsking(null)}
            >
              Keep my sets
            </button>
          </div>
        </div>
      )}
      {problem && (
        <p role="alert" className="status-error m-0">
          {problem}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
    </section>
  )
}
