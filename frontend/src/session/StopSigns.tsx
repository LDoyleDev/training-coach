import { STOP_SIGNS } from './safety'
import { card, primary } from '../ui'

function Signs() {
  return (
    <ul className="m-0 flex flex-col gap-2 pl-5">
      {STOP_SIGNS.map(({ signs, then }) => (
        <li key={signs}>
          <strong>{signs}:</strong> {then}
        </li>
      ))}
    </ul>
  )
}

/** The stop signs before a person's first guided session (spec B7); the server remembers it
 * was read, so it shows once on any device. */
export function StopSignsCard({ onRead }: { onRead: () => void }) {
  return (
    <section aria-labelledby="stop-signs" className={`${card} flex flex-col gap-3`}>
      <h2 id="stop-signs" className="m-0 text-2xl font-extrabold">
        Before you start: stop signs
      </h2>
      <Signs />
      <p className="m-0">They are always one tap away during a session, under Stop signs.</p>
      <button type="button" className={primary} onClick={onRead}>
        Got it, start
      </button>
    </section>
  )
}

/** The stop signs one tap away in the guided session. */
export function StopSignsTap() {
  return (
    <details className={card}>
      <summary className="min-h-11 cursor-pointer font-bold">Stop signs</summary>
      <div className="mt-2">
        <Signs />
      </div>
    </details>
  )
}
