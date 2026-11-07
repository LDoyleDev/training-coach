import { AllStopSigns } from '../session/StopSigns'
import { card } from '../ui'
import { NOT_EXAMINED, NOTES, WITH_EVERY_NOTE, type Note } from './questions'

/** The note the health answers lead to, with the lines every note carries (ADR-0085). Shown
 * on this device only; it never blocks anything. */
export default function NoteCard({ note }: { note: Note }) {
  const { title, text } = NOTES[note]
  return (
    <section aria-labelledby="health-note" className={`${card} flex flex-col gap-3`} role="status">
      <h2 id="health-note" className="m-0 text-2xl font-extrabold">
        {title}
      </h2>
      <p className="m-0">{text}</p>
      <ul className="m-0 flex flex-col gap-2 pl-5">
        {WITH_EVERY_NOTE.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <AllStopSigns />
      <p className="m-0 text-[var(--slate)]">{NOT_EXAMINED}</p>
    </section>
  )
}
