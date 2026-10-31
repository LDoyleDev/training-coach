import { card } from './ui'

/** What a visitor from outside the EU and EEA sees (ADR-0085), as the server's own 451 page. */
export default function Unavailable() {
  return (
    <main className="mx-auto max-w-xl p-4">
      <div className={card}>
        <h1 className="m-0 mb-3">Not available in your region</h1>
        <p className="m-0">Training Coach is only for people in the EU and EEA.</p>
      </div>
    </main>
  )
}
