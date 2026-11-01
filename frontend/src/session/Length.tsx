import type { Guided, GuidedItem, Length } from '../api'
import type { Minutes } from './logic'
import { card, small } from '../ui'
import { LAST_SET, LAST_SET_LINE } from './safety'

const option = (on: boolean) =>
  'min-h-11 rounded-xl border-2 px-3 font-bold disabled:opacity-60 ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/**
 * Short on time today (ADR-0082): As planned, 40, 30 or 20 min, for today's session only; the
 * plan doesn't change. The person picks; nothing is recommended. Once a set is kept the length
 * is fixed and shows as words. What the length drops is named before Start. With no choice for
 * the day, the person's time per session on Account is shown as chosen, said to be theirs, and
 * As planned stays a choice for the day.
 */
export default function LengthChoice({
  session,
  length,
  busy,
  onChoose,
  onLastSet,
}: {
  session: Guided
  length: Length
  busy: boolean
  onChoose: (minutes: Minutes) => void
  onLastSet: (on: boolean) => void
}) {
  const chosen = length.minutes
  const mine = length.from_setting ? ' (your time per session)' : ''
  // Offered with a shorter day (ADR-0084): not while locked, nor with nothing it applies to.
  const lastSet = length.last_set ?? null
  const choices: Minutes[] = [null, ...(length.options as NonNullable<Minutes>[])]
  return (
    <section aria-labelledby="length" className={card + ' flex flex-col gap-3'}>
      <h2 id="length" className="m-0 text-lg font-bold">
        Short on time today?
      </h2>
      {length.fixed ? (
        <p className="m-0">
          {chosen === null ? 'As planned' : `${chosen} min`} today{mine}, about {session.minutes}{' '}
          min. It stays like this now a set is kept.
        </p>
      ) : (
        <>
          <div role="group" aria-labelledby="length" className="grid grid-cols-4 gap-2">
            {choices.map((minutes) => (
              <button
                key={String(minutes)}
                type="button"
                aria-pressed={chosen === minutes}
                className={option(chosen === minutes)}
                disabled={busy}
                onClick={() => chosen !== minutes && onChoose(minutes)}
              >
                {minutes === null ? 'As planned' : `${minutes} min`}
              </button>
            ))}
          </div>
          <p className="m-0 text-sm text-[var(--slate)]">
            {chosen === null
              ? `About ${length.planned_minutes} min as planned. For today only; the plan stays the same.`
              : length.from_setting
                ? `${chosen} min is your time per session, set on Account: about ${session.minutes} min, warm-up included. As planned today: about ${length.planned_minutes} min.`
                : `About ${session.minutes} min at this length, warm-up included. As planned: about ${length.planned_minutes} min.`}
          </p>
        </>
      )}
      {!length.fixed && chosen !== null && lastSet !== null && (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            aria-pressed={lastSet}
            className={option(lastSet)}
            disabled={busy}
            onClick={() => onLastSet(!lastSet)}
          >
            {lastSet ? `✓ ${LAST_SET}` : LAST_SET}
          </button>
          <p className="m-0 text-sm text-[var(--slate)]">{LAST_SET_LINE}</p>
        </div>
      )}
      {length.shortest !== null && (
        <p className="m-0 font-bold">
          The shortest this session gets is {length.shortest} minutes. The session below is that
          version.
        </p>
      )}
      {length.dropped.length > 0 && (
        <p className="m-0">Dropped today: {length.dropped.join(', ')}.</p>
      )}
    </section>
  )
}

/** Keep on an exercise in the overview: pinned, a shorter day never drops it (ADR-0082). */
export function KeepToggle({
  item,
  length,
  busy,
  onToggle,
}: {
  item: GuidedItem
  length: Length
  busy: boolean
  onToggle: (keep: string[], text: string) => void
}) {
  const kept = length.keep.includes(item.slug)
  const toggle = () =>
    kept
      ? onToggle(
          length.keep.filter((slug) => slug !== item.slug),
          `${item.name} can be dropped again.`,
        )
      : onToggle([...length.keep, item.slug], `${item.name} stays in today.`)
  return (
    <button
      type="button"
      aria-pressed={kept}
      aria-label={`Keep ${item.name}`}
      className={small + ' disabled:opacity-60'}
      disabled={busy}
      onClick={toggle}
    >
      {kept ? '✓ Keep' : 'Keep'}
    </button>
  )
}
