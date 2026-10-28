import type { Top } from '../api'
import { KIT_HREF } from '../account/kit'
import { moveHref } from './ladder'

/** Exercises that met the ready rule with no level to move to, in the saved screen's words
 * (ADR-0078): the top of the ladder, or the last level the kit allows with what opens the next
 * one and a link to My equipment (ADR-0071). Said in the week it was first met; nothing moves.
 * Each name links to its ladder on the Plan page (ADR-0075). */
export function TopList({ top }: { top: Top[] }) {
  return (
    <ul className="m-0 flex flex-col gap-1 pl-5">
      {top.map((t) => (
        <li key={t.slug}>
          <a href={moveHref(t.slug)} className="font-bold underline">
            {t.exercise}
          </a>
          {t.unlock ? (
            <>
              : top of the range on the last level your kit allows.{' '}
              {t.unlock[0].toUpperCase() + t.unlock.slice(1)}.{' '}
              <a href={KIT_HREF} className="font-bold underline">
                My equipment
              </a>
            </>
          ) : (
            ': top of the range on the last level of its ladder.'
          )}
        </li>
      ))}
    </ul>
  )
}

/** The list under its own heading, for Home's Progress card; nothing when there is none. */
export default function TopNotes({ top }: { top: Top[] }) {
  if (top.length === 0) return null
  return (
    <div className="flex flex-col gap-1">
      <p className="m-0 font-bold">At the top:</p>
      <TopList top={top} />
    </div>
  )
}
