import { useState } from 'react'
import { card, danger, primary, primaryInline, secondary, small } from '../ui'
import {
  LIMITS,
  SETTING_NAMES,
  buildSchedule,
  formatDuration,
  fromDraft,
  parseSetting,
  toDraft,
  totalSeconds,
  type Draft,
  type HiitSettings,
  type SettingName,
} from './logic'
import { loadPresets, newId, savePresets, type Preset } from './presets'

const sameSettings = (a: HiitSettings, b: HiitSettings) => SETTING_NAMES.every((n) => a[n] === b[n])

const NAMES: Record<SettingName, string> = {
  prepare: 'Prepare',
  work: 'Work',
  rest: 'Rest',
  cycles: 'Cycles',
  sets: 'Sets',
  setRest: 'Rest between sets',
  coolDown: 'Cool down',
}

const HINTS: Record<SettingName, string> = {
  prepare: 'seconds',
  work: 'seconds',
  rest: 'seconds',
  cycles: 'work + rest, per set',
  sets: 'times through the cycles',
  setRest: 'seconds',
  coolDown: 'seconds, 0 for none',
}

function Stepper(props: {
  name: SettingName
  value: string
  /** What an empty or invalid field means: the same value Start would use. */
  fallback: number
  onChange: (value: string) => void
}) {
  const { name, value, fallback, onChange } = props
  const { min, max, step } = LIMITS[name]
  const id = `hiit-${name}`
  const current = parseSetting(name, value, fallback)
  const label = NAMES[name].toLowerCase()
  return (
    <div className="flex items-center gap-2">
      <div className="min-w-0 flex-1 leading-tight">
        <label htmlFor={id} className="font-bold">
          {NAMES[name]}
        </label>
        <p className="text-sm text-[var(--slate)]">{HINTS[name]}</p>
      </div>
      <button
        type="button"
        className={small + ' min-w-12 text-2xl'}
        aria-label={`Less ${label}`}
        disabled={current <= min}
        onClick={() => onChange(String(Math.max(min, current - step)))}
      >
        −
      </button>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        className="num w-16 rounded-xl border-2 border-[var(--line)] bg-transparent py-2 text-center text-xl font-bold"
        onChange={(e) => onChange(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={() => onChange(String(current))}
      />
      <button
        type="button"
        className={small + ' min-w-12 text-2xl'}
        aria-label={`More ${label}`}
        disabled={current >= max}
        onClick={() => onChange(String(Math.min(max, current + step)))}
      >
        +
      </button>
    </div>
  )
}

/** The saved workouts: pick one to load it, save the current values, rename by saving anew. */
function SavedWorkouts(props: {
  settings: HiitSettings
  onPick: (settings: HiitSettings) => void
}) {
  const { settings, onPick } = props
  const [presets, setPresets] = useState<Preset[]>(loadPresets)
  const [selected, setSelected] = useState(
    () => presets.find((p) => sameSettings(p.settings, settings))?.id ?? null,
  )
  const [naming, setNaming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const chosen = presets.find((p) => p.id === selected) ?? null
  const changed = chosen !== null && !sameSettings(chosen.settings, settings)

  const store = (next: Preset[]) => {
    setPresets(next)
    savePresets(next)
  }
  const saveNew = () => {
    const name = (naming ?? '').trim().slice(0, 40)
    if (!name) return
    const preset = { id: newId(), name, settings }
    store([...presets, preset])
    setSelected(preset.id)
    setNaming(null)
  }

  return (
    <section aria-labelledby="hiit-saved" className="flex flex-col gap-2">
      <h3 id="hiit-saved" className="font-bold">
        Saved workouts
      </h3>
      {presets.length === 0 ? (
        <p className="text-[var(--slate)]">None saved yet.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                aria-pressed={p.id === selected}
                className={p.id === selected ? primaryInline : small}
                onClick={() => {
                  setSelected(p.id)
                  setDeleting(false)
                  onPick(p.settings)
                }}
              >
                {p.name}{' '}
                <span className="font-normal">
                  {formatDuration(totalSeconds(buildSchedule(p.settings)))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {naming !== null ? (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            saveNew()
          }}
        >
          <input
            aria-label="Workout name"
            placeholder="Name, e.g. Bike sprints"
            maxLength={40}
            autoFocus
            value={naming}
            className="min-w-0 flex-1 rounded-xl border-2 border-[var(--line)] bg-transparent px-3"
            onChange={(e) => setNaming(e.target.value)}
          />
          <button type="submit" className={primaryInline} disabled={!naming.trim()}>
            Save
          </button>
          <button type="button" className={small} onClick={() => setNaming(null)}>
            Cancel
          </button>
        </form>
      ) : deleting && chosen ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="flex-1 font-bold">Delete {chosen.name}?</p>
          <button
            type="button"
            className={danger}
            onClick={() => {
              store(presets.filter((p) => p.id !== chosen.id))
              setSelected(null)
              setDeleting(false)
            }}
          >
            Delete
          </button>
          <button type="button" className={small} onClick={() => setDeleting(false)}>
            Keep
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {chosen && changed && (
            <button
              type="button"
              className={small}
              onClick={() =>
                store(presets.map((p) => (p.id === chosen.id ? { ...p, settings } : p)))
              }
            >
              Save changes to {chosen.name}
            </button>
          )}
          <button type="button" className={small} onClick={() => setNaming('')}>
            Save as new
          </button>
          {chosen && (
            <button type="button" className={danger} onClick={() => setDeleting(true)}>
              Delete {chosen.name}
            </button>
          )}
        </div>
      )}
    </section>
  )
}

/** The setup step: saved workouts, the seven settings, the totals, voice, Start. */
export default function HiitSetup(props: {
  draft: Draft
  fallback: HiitSettings
  onDraft: (draft: Draft) => void
  /** Null when this browser can't speak. */
  voice: boolean | null
  onVoice: (on: boolean) => void
  onStart: () => void
  onCancel?: () => void
}) {
  const { draft, fallback, onDraft, voice, onVoice, onStart, onCancel } = props
  const settings = fromDraft(draft, fallback)
  const schedule = buildSchedule(settings)
  return (
    <section aria-labelledby="hiit-title" className={card + ' flex flex-col gap-4'}>
      <h2 id="hiit-title">HIIT timer</h2>
      <SavedWorkouts settings={settings} onPick={(s) => onDraft(toDraft(s))} />
      <div className="flex flex-col gap-3">
        {SETTING_NAMES.map((name) => (
          <Stepper
            key={name}
            name={name}
            value={draft[name]}
            fallback={fallback[name]}
            onChange={(value) => onDraft({ ...draft, [name]: value })}
          />
        ))}
      </div>
      <p className="text-[var(--slate)]">
        Total{' '}
        <span className="font-bold text-[var(--ink)]">
          {formatDuration(totalSeconds(schedule))}
        </span>{' '}
        · <span className="font-bold text-[var(--ink)]">{schedule.length}</span> intervals
      </p>
      {voice !== null && (
        <label className="flex min-h-11 items-center gap-3 font-bold">
          <input
            type="checkbox"
            className="size-6 accent-[var(--bell-ink)]"
            checked={voice}
            onChange={(e) => onVoice(e.target.checked)}
          />
          Voice cues
        </label>
      )}
      <button type="button" className={primary} onClick={onStart}>
        Start
      </button>
      {onCancel && (
        <button type="button" className={secondary} onClick={onCancel}>
          Cancel
        </button>
      )}
    </section>
  )
}
