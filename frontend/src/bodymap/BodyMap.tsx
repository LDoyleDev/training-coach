import { useEffect, useState } from 'react'
import { fetchCoverage, type Band, type Coverage, type MuscleCoverage } from '../api'
import { HEAD, HEIGHT, MIRROR, REGIONS, SILHOUETTE, WIDTH, type View } from './regions'
import {
  BANDS,
  amount,
  bandLabel,
  goal,
  muscleName,
  sessionWarnings,
  sets,
  warnings,
} from './words'

type State =
  | { status: 'loading' }
  | { status: 'hidden' }
  | { status: 'error'; message: string }
  | { status: 'ready'; coverage: Coverage }

const slug = (s: string) => s.replace(/ /g, '-')
const fill = (band: Band) => `var(--band-${slug(band)})`

type FigureProps = {
  view: View
  bands: Map<string, Band>
  selected: string | null
  onSelect: (muscle: string) => void
}

/** One mannequin with its muscles coloured. The list below is the accessible way in; tapping
 * a region is a shortcut to the same row. */
function BodyFigure({ view, bands, selected, onSelect }: FigureProps) {
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
          fill={fill(bands.get(r.muscle) ?? 'grey')}
          stroke={r.muscle === selected ? 'var(--ink)' : 'var(--fig-near-line)'}
          strokeWidth={r.muscle === selected ? 2 : 0.75}
          className="cursor-pointer"
          onClick={() => onSelect(r.muscle)}
        />
      ))}
    </>
  )
  return (
    <figure className="m-0 flex flex-1 flex-col items-center">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full max-w-[11rem]"
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
      <figcaption className="text-sm text-[var(--slate)]">
        {view === 'front' ? 'Front' : 'Back'}
      </figcaption>
    </figure>
  )
}

function Swatch({ band }: { band: Band }) {
  return (
    <span
      className="inline-block h-3 w-3 shrink-0 rounded-sm border border-[var(--fig-near-line)]"
      style={{ background: fill(band) }}
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

/** The read-only body map on the Plan tab (program-builder.md F, step 3): what the plan as it
 * stands gives each muscle in a week. */
export function BodyMap() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchCoverage(ctrl.signal)
      .then((coverage) => setState(coverage ? { status: 'ready', coverage } : { status: 'hidden' }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => ctrl.abort()
  }, [])

  if (state.status === 'loading') return <p className="status">Loading the body map…</p>
  if (state.status === 'hidden') return null
  if (state.status === 'error')
    return (
      <p className="status status-error" role="alert">
        Couldn't load the body map. {state.message}
      </p>
    )

  const { coverage } = state
  const bands = new Map(coverage.muscles.map((m) => [m.muscle, m.band]))
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
        <BodyFigure view="front" bands={bands} selected={open} onSelect={select} />
        <BodyFigure view="back" bands={bands} selected={open} onSelect={select} />
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
