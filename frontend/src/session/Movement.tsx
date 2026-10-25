import { useState } from 'react'
import Figure from '../figures/Figure'
import { FIGURES } from '../figures/poses'

/** How the exercise moves, under its how-to on the set screen: the mannequin (ADR-0063), for an
 * exercise that has one. The drawing is tall, so it folds away to keep the counter in view: open
 * on an exercise's first set, closed on the sets after. */
export default function Movement({
  slug,
  name,
  open,
}: {
  slug: string
  name: string
  open: boolean
}) {
  const [shown, setShown] = useState(open)
  if (!(slug in FIGURES)) return null
  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        aria-expanded={shown}
        className="min-h-11 self-start font-bold text-[var(--bell-ink)] underline"
        onClick={() => setShown((s) => !s)}
      >
        {shown ? 'Hide the movement' : 'Show the movement'}
      </button>
      {shown && <Figure slug={slug} name={name} />}
    </div>
  )
}
