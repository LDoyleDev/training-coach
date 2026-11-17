import type { EasyStart } from '../api'
import { card, primaryInline, secondary } from '../ui'

/** What "One more easy week" keeps, by the phase it brings back. */
const WEEK = {
  light: 'Stay on one set of each for another week.',
  lower: 'Stay on one set fewer for another week.',
}

/**
 * The easy start's offers on Today (ADR-0094), each a tap the person can leave: after 14 days
 * or more without a workout, "Start the easy start again" (Decided 9; it stands in for Ease back
 * in on that return, so there is one prompt); after a step up, "One more easy week" while it's
 * new (Decided 8 and 17). Nothing shows while neither is on offer.
 */
export default function EasyStartOffers({
  easy,
  busy,
  onTake,
}: {
  easy: EasyStart | null
  busy: boolean
  onTake: (offer: 'extend' | 'restart') => void
}) {
  if (easy?.restart)
    return (
      <section aria-labelledby="easy-restart" className={card + ' flex flex-col gap-2'}>
        <h2 id="easy-restart" className="m-0 text-xl font-extrabold">
          Start the easy start again
        </h2>
        <p className="m-0">It's been 14 days or more since your last session.</p>
        <button
          type="button"
          className={`${primaryInline} self-start`}
          disabled={busy}
          onClick={() => onTake('restart')}
        >
          Start it again
        </button>
      </section>
    )
  if (easy?.extend)
    return (
      <section aria-label="One more easy week" className={card + ' flex flex-col gap-2'}>
        <p className="m-0">{WEEK[easy.extend]}</p>
        <button
          type="button"
          className={`${secondary} self-start`}
          disabled={busy}
          onClick={() => onTake('extend')}
        >
          One more easy week
        </button>
      </section>
    )
  return null
}
