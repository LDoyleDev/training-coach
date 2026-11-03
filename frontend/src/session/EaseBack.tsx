import type { Guided } from '../api'
import { card, primaryInline, secondary } from '../ui'

export const EASE_BACK = 'Ease back in: one step down today'

/** One prompt for a return after three weeks or more away (ADR-0084), however many exercises it
 * covers: each one step down for today only, levels unchanged. A suggestion; the person decides,
 * and it is asked once per return. */
export default function EaseBack({
  ease,
  busy,
  onAnswer,
}: {
  ease: Guided['ease_back']
  busy: boolean
  onAnswer: (ease: boolean) => void
}) {
  return (
    <section aria-labelledby="ease-back" className={card + ' flex flex-col gap-2'}>
      <h2 id="ease-back" className="m-0 text-xl font-extrabold">
        {EASE_BACK}
      </h2>
      <p className="m-0">
        It's been three weeks or more since you last did{' '}
        {ease.length === 1 ? 'this exercise' : 'these exercises'}. For today only:
      </p>
      <ul className="m-0 pl-6">
        {ease.map((e) => (
          <li key={e.exercise}>
            {e.exercise} at {e.step}
          </li>
        ))}
      </ul>
      <p className="m-0">Your levels stay as they are.</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={primaryInline}
          disabled={busy}
          onClick={() => onAnswer(true)}
        >
          One step down today
        </button>
        <button type="button" className={secondary} disabled={busy} onClick={() => onAnswer(false)}>
          Not today
        </button>
      </div>
    </section>
  )
}
