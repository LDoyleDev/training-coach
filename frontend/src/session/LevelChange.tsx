import { useState } from 'react'
import type { ItemLevel } from '../api'
import { confirmText, lockedText, needs } from '../plan/ladder'
import { actions, primaryInline, secondary, small } from '../ui'
import { nearby, type LevelScope } from './levels'

/**
 * The step on the set screen, with "Change level" (ADR-0080): the ladder one level down and up
 * first, every level on request, locked levels said in words (ADR-0071, ADR-0083). Picking a level asks
 * "For today" (this session only) or "From now on" (the person's level, as on the Plan tab).
 * `onPick` answers true once changed, which closes the picker. `noKit`: away, today's step is
 * below the person's level because theirs needs kit (ADR-0086); their level stays.
 */
export default function LevelChange({
  name,
  step,
  level,
  noKit = false,
  done,
  busy,
  onPick,
}: {
  name: string
  step: string // today's, as the set screen shows it
  level: ItemLevel
  noKit?: boolean
  done: number // sets of this exercise confirmed so far
  busy: boolean
  onPick: (stepId: number, stepName: string, scope: LevelScope) => Promise<boolean>
}) {
  const [open, setOpen] = useState(false)
  const [all, setAll] = useState(false)
  const [picked, setPicked] = useState(level.step_id)
  const rungs = all ? level.ladder : nearby(level)
  const chosen = level.ladder.find((r) => r.id === picked)
  const locked = chosen ? lockedText(chosen.name, chosen) : null
  const changing = chosen !== undefined && picked !== level.step_id

  const pick = async (scope: LevelScope) => {
    if (chosen && (await onPick(chosen.id, chosen.name, scope))) setOpen(false)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="m-0 text-[var(--slate)]">
          {step}
          {noKit ? (
            <span className="font-bold"> · No-equipment step today</span>
          ) : (
            level.for_today && <span className="font-bold"> · for today only</span>
          )}
        </p>
        {!open && (
          <button
            type="button"
            className={small}
            onClick={() => {
              setPicked(level.step_id)
              setAll(false)
              setOpen(true)
            }}
          >
            Change level
          </button>
        )}
      </div>
      {open && (
        <fieldset className="m-0 flex flex-col gap-2 rounded-xl border-2 border-[var(--line)] p-3">
          <legend className="px-1 font-bold">Level for {name}</legend>
          {rungs.map((r) => (
            <label key={r.id} className="flex min-h-11 items-start gap-3 py-1">
              <input
                type="radio"
                name={`level-${name}`}
                value={r.id}
                checked={picked === r.id}
                onChange={() => setPicked(r.id)}
                className="mt-0.5 size-5 shrink-0"
              />
              <span className="flex flex-col">
                <span>
                  {r.name}
                  {r.id === level.step_id && ' (today)'}
                  {needs(r) && ` · Locked: ${needs(r)}`}
                </span>
                {r.cue && <span className="text-sm text-[var(--slate)]">{r.cue}</span>}
              </span>
            </label>
          ))}
          {level.ladder.length > rungs.length || all ? (
            <button
              type="button"
              className={small + ' self-start'}
              aria-expanded={all}
              onClick={() => setAll((cur) => !cur)}
            >
              {all ? 'Fewer levels' : `All levels (${level.ladder.length})`}
            </button>
          ) : null}
          {changing && (
            <>
              <p className="m-0">{confirmText(chosen.name)}</p>
              {locked && <p className="m-0">{locked} You can still choose it.</p>}
              {done > 0 && (
                <p className="m-0">
                  {done === 1 ? 'The set you’ve done stays' : `The ${done} sets you’ve done stay`}{' '}
                  at {step}.
                </p>
              )}
              <p className="m-0 font-bold">For today, or from now on?</p>
              <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[var(--slate)]">
                <li>For today: only this session. Your level stays as it is.</li>
                <li>From now on: your level changes, for the next sessions too.</li>
              </ul>
            </>
          )}
          <div className={actions}>
            {changing && (
              <>
                <button
                  type="button"
                  className={primaryInline}
                  disabled={busy}
                  onClick={() => void pick('today')}
                >
                  For today
                </button>
                <button
                  type="button"
                  className={secondary}
                  disabled={busy}
                  onClick={() => void pick('from_now_on')}
                >
                  From now on
                </button>
              </>
            )}
            <button type="button" className={secondary} onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </fieldset>
      )}
    </div>
  )
}
