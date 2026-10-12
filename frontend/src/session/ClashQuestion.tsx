import { useState } from 'react'
import type { Answer, Clash } from '../api'
import { dayText, recentDays } from './logic'
import { actions, card, primaryInline, secondary } from '../ui'

const what = (clash: Clash) => clash.recorded.map((r) => `${r.name} (${r.summary})`).join(' and ')

/**
 * The question when a log would land on a day that already has its session (ADR-0060):
 * what is there, then Replace it, Move it to another day, Add it to that day, or Cancel.
 * Nothing is saved until an answer is sent with the same save. ``taken`` is the day a move
 * was refused for, because it holds a session too.
 */
export default function ClashQuestion({
  clash,
  taken,
  busy,
  onAnswer,
  onCancel,
}: {
  clash: Clash
  taken?: Clash | null
  busy?: boolean
  onAnswer: (answer: Answer) => void
  onCancel: () => void
}) {
  const [moving, setMoving] = useState(Boolean(taken))
  const seen = clash.recorded.map((r) => r.workout_id)
  const answer = (resolution: string) => onAnswer({ resolution, seen })
  const one = clash.recorded.length === 1
  return (
    <section
      role="alertdialog"
      aria-labelledby="clash-title"
      className={`${card} flex flex-col gap-3`}
    >
      <h2 id="clash-title" className="m-0 text-xl font-extrabold">
        {dayText(clash.day)} already has a session
      </h2>
      <ul className="m-0 flex flex-col gap-1 pl-5">
        {clash.recorded.map((r) => (
          <li key={r.workout_id}>
            <span className="font-bold">{r.name}</span>: {r.summary}
          </li>
        ))}
      </ul>
      {taken && (
        <p role="status" className="status">
          {dayText(taken.day)} has {what(taken)} too. Pick another day.
        </p>
      )}
      {moving ? (
        <fieldset className="flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 font-bold">Move {one ? 'it' : 'them'} to</legend>
          <div className={actions}>
            {recentDays()
              .filter((day) => day !== clash.day && day !== taken?.day)
              .map((day) => (
                <button
                  key={day}
                  type="button"
                  className={secondary}
                  disabled={busy}
                  onClick={() => answer(`move:${day}`)}
                >
                  {dayText(day)}
                </button>
              ))}
          </div>
          <button type="button" className={secondary} onClick={() => setMoving(false)}>
            Back
          </button>
        </fieldset>
      ) : (
        <>
          <p className="m-0">What should happen to {one ? 'it' : 'them'}?</p>
          <div className={actions}>
            <button
              type="button"
              className={primaryInline}
              disabled={busy}
              onClick={() => answer('replace')}
            >
              Replace {one ? 'it' : 'them'}
            </button>
            <button type="button" className={secondary} onClick={() => setMoving(true)}>
              Move {one ? 'it' : 'them'} to another day
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy}
              onClick={() => answer('add')}
            >
              Add to that day
            </button>
            <button type="button" className={secondary} onClick={onCancel}>
              Cancel
            </button>
          </div>
        </>
      )}
    </section>
  )
}
