import { useState } from 'react'
import {
  type Band,
  type Coverage,
  type Heat,
  type ItemMuscle,
  type MuscleCoverage,
  type SessionCoverage,
} from '../api'
import { HEAD, HEIGHT, MIRROR, REGIONS, SILHOUETTE, WIDTH, type View } from './regions'
import type { State } from './useCoverage'
import {
  BANDS,
  HEATS,
  amount,
  bandLabel,
  goal,
  heatLabel,
  muscleName,
  sessionWarnings,
  sets,
  warnings,
  weightHeat,
} from './words'

const slug = (s: string) => s.replace(/ /g, '-')
const fill = (band: Band) => `var(--band-${slug(band)})`
const heatFill = (heat: Heat) => (heat === 'over' ? fill('warning') : `var(--heat-${heat})`)

type FigureProps = {
  view: View
  fills: Map<string, string> // muscle -> its colour; the rest are not worked
  selected?: string | null
  onSelect?: (muscle: string) => void // none: a picture only, nothing to tap
  small?: boolean // the set screen's, beside an exercise's how-to
}

/** One mannequin with its muscles coloured. The list below is the accessible way in; tapping
 * a region is a shortcut to the same row. */
function BodyFigure({ view, fills, selected = null, onSelect, small = false }: FigureProps) {
  const regions = REGIONS[view]
  const half = (
    <>
      {SILHOUETTE.map((d) => (
        <path key={d} d={d} fill="var(--fig-near-base)" stroke="var(--fig-near-line)" />
      ))}
      {regions.map((r) => (
        <path
          key={r.muscle}
          d={r.d}
          data-muscle={r.muscle}
          fill={fills.get(r.muscle) ?? fill('grey')}
          stroke={r.muscle === selected ? 'var(--ink)' : 'var(--fig-near-line)'}
          strokeWidth={r.muscle === selected ? 2 : 0.75}
          className={onSelect ? 'cursor-pointer' : undefined}
          onClick={onSelect ? () => onSelect(r.muscle) : undefined}
        />
      ))}
    </>
  )
  return (
    <figure
      className={
        small ? 'm-0 flex w-14 flex-col items-center' : 'm-0 flex flex-1 flex-col items-center'
      }
    >
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={small ? 'h-auto w-full' : 'h-auto w-full max-w-[11rem]'}
        aria-hidden="true"
        strokeLinejoin="round"
      >
        <circle
          cx={HEAD.cx}
          cy={HEAD.cy}
          r={HEAD.r}
          fill="var(--fig-near-base)"
          stroke="var(--fig-near-line)"
        />
        {half}
        <g transform={MIRROR}>{half}</g>
      </svg>
      <figcaption className={`${small ? 'text-xs' : 'text-sm'} text-[var(--slate)]`}>
        {view === 'front' ? 'Front' : 'Back'}
      </figcaption>
    </figure>
  )
}

/** The muscles one exercise works, on two small figures beside its how-to on the set screen,
 * coloured as the session map is: the main mover darkest. A picture only, hidden from assistive
 * tech: the words beside it say the same. */
export function ExerciseFigures({
  muscles,
  className = '',
}: {
  muscles: readonly ItemMuscle[]
  className?: string
}) {
  const fills = new Map(muscles.map((m) => [m.muscle, heatFill(weightHeat(m.weight))]))
  return (
    <div className={`flex gap-1 ${className}`} aria-hidden="true">
      <BodyFigure view="front" fills={fills} small />
      <BodyFigure view="back" fills={fills} small />
    </div>
  )
}

function Swatch({ band, colour }: { band?: Band; colour?: string }) {
  return (
    <span
      className="inline-block h-3 w-3 shrink-0 rounded-sm border border-[var(--fig-near-line)]"
      style={{ background: colour ?? fill(band ?? 'grey') }}
      aria-hidden="true"
    />
  )
}

function MuscleRow({
  m,
  coverage,
  open,
  onToggle,
}: {
  m: MuscleCoverage
  coverage: Coverage
  open: boolean
  onToggle: () => void
}) {
  const found = warnings(m, coverage)
  return (
    <li id={`muscle-${slug(m.muscle)}`} className="border-b border-[var(--line)]">
      <button
        type="button"
        aria-expanded={open}
        aria-label={`${muscleName(m.muscle)}: ${sets(m.sets)} sets, ${bandLabel(m.band)}${found.length > 0 ? ', has a warning' : ''}`}
        onClick={onToggle}
        className="flex w-full items-center gap-3 bg-transparent py-2 text-left text-[var(--ink)]"
      >
        <Swatch band={m.band} />
        <span className="flex-1">
          {muscleName(m.muscle)}
          {found.length > 0 && <span className="ml-2 text-[var(--bell-ink)]">!</span>}
        </span>
        <span className="num font-bold">{sets(m.sets)}</span>
        <span className="w-28 text-right text-sm text-[var(--slate)]">{bandLabel(m.band)}</span>
      </button>
      {open && (
        <div className="pb-3 pl-6 text-[0.9375rem]">
          <p className="m-0">{amount(m)}.</p>
          <p className="m-0 text-[var(--slate)]">
            {goal(m)}.{m.evidence === 'low' && ' Low evidence for this band.'}
            {m.evidence === 'very low' && ' Very low evidence for this band.'}
          </p>
          {found.length > 0 && (
            <ul className="my-2 pl-5 text-[var(--bell-ink)]">
              {found.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          {m.sources.length > 0 && (
            <ul className="mt-2 mb-0 list-none p-0 text-[var(--slate)]">
              {m.sources.map((s) => (
                <li key={`${s.session}-${s.exercise}`}>
                  {s.session} · {s.exercise}: {s.sets} × {sets(s.weight)} ={' '}
                  {sets(s.sets * s.weight)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  )
}

/** The read-only body map on the Plan page (program-builder.md F, step 3): what the plan as it
 * stands gives each muscle in a week. */
export function BodyMap({ state }: { state: State }) {
  const [open, setOpen] = useState<string | null>(null)

  if (state.status === 'loading') return <p className="status">Loading the body map…</p>
  if (state.status === 'hidden') return null
  if (state.status === 'error')
    return (
      <p className="status status-error" role="alert">
        Couldn't load the body map. {state.message}
      </p>
    )

  const { coverage } = state
  const fills = new Map(coverage.muscles.map((m) => [m.muscle, fill(m.band)]))
  const select = (muscle: string) => {
    setOpen(muscle)
    document
      .getElementById(`muscle-${slug(muscle)}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
  const toggle = (muscle: string) => setOpen((cur) => (cur === muscle ? null : muscle))
  const heavy = sessionWarnings(coverage)
  const main = coverage.muscles.filter((m) => m.main)
  const rest = coverage.muscles.filter((m) => !m.main)
  const rows = (list: MuscleCoverage[]) =>
    list.map((m) => (
      <MuscleRow
        key={m.muscle}
        m={m}
        coverage={coverage}
        open={open === m.muscle}
        onToggle={() => toggle(m.muscle)}
      />
    ))

  return (
    <div className="max-w-[46rem]">
      <p className="mt-0 font-bold">
        {coverage.main_on_target} of {coverage.main_total} main muscles on target
      </p>
      <div
        className="flex gap-2"
        role="img"
        aria-label={`Body map: ${coverage.main_on_target} of ${coverage.main_total} main muscles on target. The list below has every muscle.`}
      >
        <BodyFigure view="front" fills={fills} selected={open} onSelect={select} />
        <BodyFigure view="back" fills={fills} selected={open} onSelect={select} />
      </div>
      <ul className="my-3 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
        {BANDS.map((b) => (
          <li key={b.band} className="flex items-center gap-1.5">
            <Swatch band={b.band} />
            {b.label}
          </li>
        ))}
      </ul>
      {heavy.length > 0 && (
        <ul className="my-3 pl-5 text-[var(--bell-ink)]">
          {heavy.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <h3 className="mb-1 text-base">Main muscles</h3>
      <ul className="m-0 list-none p-0">{rows(main)}</ul>
      <h3 className="mt-4 mb-1 text-base">The rest</h3>
      <ul className="m-0 list-none p-0">{rows(rest)}</ul>
      <p className="mt-3 text-sm text-[var(--slate)]">
        Sets are counted by how much each exercise works a muscle: 1 for the main mover, ½ or ¼ for
        a helper. A muscle is on target in its green band on two days a week. Tap a muscle, on the
        figure or in the list, to see where its sets come from. The spine, grip and rest-day
        warnings are rules of thumb, not study results.
      </p>
    </div>
  )
}

/** One session's map, at the top of its row on the Plan page (ADR-0069): how hard this session
 * works each muscle, scaled to one session rather than the week's bands. Tapping a muscle says
 * how many of its sets come from here, and from which exercises. */
export function SessionMap({ coverage, day }: { coverage: Coverage; day: SessionCoverage }) {
  const [open, setOpen] = useState<string | null>(null)
  if (day.muscles.length === 0) return null
  const fills = new Map(day.muscles.map((m) => [m.muscle, heatFill(m.heat)]))
  const shown = day.muscles.find((m) => m.muscle === open)
  const from = shown
    ? (coverage.muscles
        .find((m) => m.muscle === shown.muscle)
        ?.sources.filter((s) => s.session === day.session) ?? [])
    : []
  const toggle = (muscle: string) => setOpen((cur) => (cur === muscle ? null : muscle))
  const hard = day.muscles.filter((m) => m.heat === 'hard' || m.heat === 'over')
  return (
    <div className="mb-4 max-w-[46rem]">
      <div
        className="flex gap-2"
        role="img"
        aria-label={`What ${day.session} works: ${
          hard.length > 0
            ? `hardest on ${hard.map((m) => muscleName(m.muscle)).join(', ')}`
            : 'no muscle worked hard'
        }. The list below has every muscle it works.`}
      >
        <BodyFigure view="front" fills={fills} selected={open} onSelect={toggle} />
        <BodyFigure view="back" fills={fills} selected={open} onSelect={toggle} />
      </div>
      <ul className="my-2 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
        {HEATS.filter((h) => h.heat !== 'none').map((h) => (
          <li key={h.heat} className="flex items-center gap-1.5">
            <Swatch colour={heatFill(h.heat)} />
            {h.label}
          </li>
        ))}
      </ul>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {day.muscles.map((m) => (
          <li key={m.muscle}>
            <button
              type="button"
              aria-pressed={open === m.muscle}
              aria-label={`${muscleName(m.muscle)}: ${sets(m.sets)} sets, ${heatLabel(m.heat)}`}
              onClick={() => toggle(m.muscle)}
              className="flex min-h-11 items-center gap-1.5 rounded-lg border border-[var(--line)] bg-transparent px-2 text-sm text-[var(--ink)] aria-pressed:border-[var(--ink)]"
            >
              <Swatch colour={heatFill(m.heat)} />
              {muscleName(m.muscle)} <span className="num font-bold">{sets(m.sets)}</span>
            </button>
          </li>
        ))}
      </ul>
      {shown && (
        <div className="mt-2 text-[0.9375rem]" aria-live="polite">
          <p className="m-0">
            {muscleName(shown.muscle)}: {sets(shown.sets)} {shown.sets === 1 ? 'set' : 'sets'} in
            this session, {heatLabel(shown.heat).toLowerCase()}.
          </p>
          {from.length > 0 && (
            <ul className="mt-1 mb-0 list-none p-0 text-[var(--slate)]">
              {from.map((s) => (
                <li key={s.exercise}>
                  {s.exercise}: {s.sets} × {sets(s.weight)} = {sets(s.sets * s.weight)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
