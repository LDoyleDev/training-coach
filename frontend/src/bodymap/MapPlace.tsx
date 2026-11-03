import type { Place } from '../api'

const NAMES: Record<'home' | 'gym', string> = { home: 'Home', gym: 'Gym' }

const option = (on: boolean) =>
  'min-h-11 w-full rounded-xl border-2 px-4 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] bg-transparent text-[var(--ink)]')

/** Home | Gym on the Plan page (ADR-0071), for someone who trains at both: which version of each
 * session the maps count, ticked once the maps show it. Only a view: the place Today starts at
 * stays as it is. ``problem``: the other view didn't load; a tap tries again. */
export function MapPlace({
  place,
  problem,
  onChoose,
}: {
  place: Place
  problem?: string
  onChoose: (place: Place) => void
}) {
  return (
    <div className="mb-4 max-w-[24rem]">
      <div role="group" aria-label="Count the sessions at" className="grid grid-cols-2 gap-2">
        {(['home', 'gym'] as const).map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={place === p}
            className={option(place === p)}
            onClick={() => onChoose(p)}
          >
            {place === p && <span aria-hidden="true">✓ </span>}
            {NAMES[p]}
          </button>
        ))}
      </div>
      <p className="mt-2 mb-0 text-sm text-[var(--slate)]">
        {place === 'gym'
          ? 'The gym versions; a session without one counts the same at both.'
          : 'The home versions, with your own kit.'}
      </p>
      {problem && (
        <p role="alert" className="status-error mt-2 mb-0">
          Couldn't load the {place === 'gym' ? 'home' : 'gym'} view. {problem} Try again.
        </p>
      )}
    </div>
  )
}
