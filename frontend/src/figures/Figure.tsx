import { useEffect, useId, useRef, useState } from 'react'
import { blend, progress } from './body'
import { perspectiveShapes } from './perspective'
import { type Figure as Data } from './poses'
import { ORDER, shapes, type Shape, type Tone } from './shapes'
import { figureFor } from './steps'

/** Which way a figure is seen: from the side (every figure) or from the front (a few). */
export type View = 'side' | 'front'

const TONES: readonly Tone[] = ['near', 'far', 'prop', 'bell']

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function Drawn({ shape, id }: { shape: Shape; id: string }) {
  const line = {
    stroke: `var(--fig-${'tone' in shape ? shape.tone : 'prop'}-line)`,
    strokeWidth: 1,
  }
  if (shape.kind === 'floor') return <path d={shape.d} fill="var(--fig-mat)" />
  if (shape.kind === 'mat')
    return (
      <rect
        x={shape.x}
        y={shape.y}
        width={shape.width}
        height={shape.height}
        fill="var(--fig-mat)"
      />
    )
  if (shape.kind === 'ring')
    return (
      <ellipse
        cx={shape.c[0]}
        cy={shape.c[1]}
        rx={shape.r}
        ry={shape.ry ?? shape.r}
        fill="none"
        stroke={`var(--fig-${shape.tone}-base)`}
        strokeWidth={shape.width}
      />
    )
  if (shape.kind === 'ball')
    return (
      <circle
        cx={shape.c[0]}
        cy={shape.c[1]}
        r={shape.r}
        fill={`url(#${id}-${shape.tone}-ball)`}
        vectorEffect="non-scaling-stroke"
        {...line}
      />
    )
  return (
    <path
      d={shape.d}
      fill={`url(#${id}-${shape.tone})`}
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
      {...line}
    />
  )
}

/** The shapes of ``figure`` seen from ``view``, ``t`` of the way from its start to its end. */
function scene(figure: Data, view: View, t: number) {
  const at = <P,>(start: P, end: P) => (t <= 0 ? start : t >= 1 ? end : blend(start, end, t))
  const { front } = figure
  if (view === 'front' && front) {
    const drawn = perspectiveShapes(at(front.start, front.end), front.camera, front.seat, front)
    return { box: front.view, drawn, floor: false }
  }
  const pose = at(figure.start, figure.end)
  return { box: figure.view, drawn: shapes(pose, figure.props, figure.order ?? ORDER), floor: true }
}

/** One drawing of ``figure``, ``t`` of the way from its start (0) to its end (1). */
function Drawing({
  figure,
  t,
  label,
  view = 'side',
}: {
  figure: Data
  t: number
  label: string
  view?: View
}) {
  const id = 'fig' + useId().replace(/[^a-zA-Z0-9]/g, '')
  const { box, drawn, floor } = scene(figure, view, t)
  const [x0, x1, y0, y1] = box
  const inset = view === 'side' ? figure.inset : undefined
  const world = (
    <>
      {floor && (
        <line
          x1={x0}
          x2={x1}
          y1={0}
          y2={0}
          stroke="var(--fig-floor)"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      )}
      {drawn.map((shape, i) => (
        <Drawn key={i} shape={shape} id={id} />
      ))}
    </>
  )
  return (
    <svg
      viewBox={`${x0} ${-y1} ${x1 - x0} ${y1 - y0}`}
      role="img"
      aria-label={label}
      // Not the `block` utility: the app's own `.block` section style (a top rule and padding)
      // would apply to the drawing too.
      style={{ display: 'block' }}
      className="max-h-72 w-full"
    >
      <defs>
        {TONES.map((tone) => (
          <g key={tone}>
            <linearGradient id={`${id}-${tone}`} x1="0.15" y1="0" x2="0.85" y2="1">
              <stop offset="0" stopColor={`var(--fig-${tone}-lit)`} />
              <stop offset="0.45" stopColor={`var(--fig-${tone}-base)`} />
              <stop offset="1" stopColor={`var(--fig-${tone}-dark)`} />
            </linearGradient>
            <radialGradient id={`${id}-${tone}-ball`} cx="0.36" cy="0.3" r="0.75">
              <stop offset="0" stopColor={`var(--fig-${tone}-lit)`} />
              <stop offset="0.6" stopColor={`var(--fig-${tone}-base)`} />
              <stop offset="1" stopColor={`var(--fig-${tone}-dark)`} />
            </radialGradient>
          </g>
        ))}
      </defs>
      {world}
      {inset && (
        <g>
          <circle
            cx={inset.of[0]}
            cy={-inset.of[1]}
            r={inset.r}
            fill="none"
            stroke="var(--fig-floor)"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
          <clipPath id={`${id}-inset`}>
            <circle cx={inset.at[0]} cy={-inset.at[1]} r={inset.size} />
          </clipPath>
          <circle cx={inset.at[0]} cy={-inset.at[1]} r={inset.size} fill="var(--paper)" />
          <g clipPath={`url(#${id}-inset)`}>
            <g
              transform={`translate(${inset.at[0]} ${-inset.at[1]}) scale(${inset.size / inset.r}) translate(${-inset.of[0]} ${inset.of[1]})`}
            >
              {world}
            </g>
          </g>
          <circle
            cx={inset.at[0]}
            cy={-inset.at[1]}
            r={inset.size}
            fill="none"
            stroke="var(--fig-floor)"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
        </g>
      )}
    </svg>
  )
}

/** One still of an exercise's figure, ``t`` from its start (0) to its end (1); nothing for a
 * slug without a figure. */
export function FigureAt({
  slug,
  t,
  label,
  step,
  view,
}: {
  slug: string
  t: number
  label: string
  step?: string
  view?: View
}) {
  const figure = figureFor(slug, step)
  return figure ? <Drawing figure={figure} t={t} label={label} view={view} /> : null
}

/** An exercise's mannequin (ADR-0063), moving from its start to its end and back, or the two
 * positions side by side, as set up at ladder ``step``. Starts still for people who ask for less
 * motion; nothing for a slug without a figure. A figure drawn from the front as well starts
 * there, with a switch to the side. */
export default function Figure({
  slug,
  name,
  step,
}: {
  slug: string
  name: string
  step?: string
}) {
  const figure = figureFor(slug, step)
  const [still, setStill] = useState(reducedMotion)
  const [t, setT] = useState(0)
  const [view, setView] = useState<View>(figure?.front ? 'front' : 'side')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!figure || still || typeof requestAnimationFrame !== 'function') return
    let frame = 0
    let shown = true
    const begin = performance.now()
    const tick = (now: number) => {
      if (shown) setT(progress(figure, now - begin))
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    // Off screen, keep the clock but don't redraw.
    const watch =
      typeof IntersectionObserver === 'function' && box.current
        ? new IntersectionObserver(([entry]) => (shown = entry.isIntersecting))
        : null
    if (watch && box.current) watch.observe(box.current)
    return () => {
      cancelAnimationFrame(frame)
      watch?.disconnect()
    }
  }, [figure, still])

  if (!figure) return null
  const [first, last] = figure.frames
  const [x0, x1, y0, y1] = view === 'front' && figure.front ? figure.front.view : figure.view
  // Side by side when both fit at full height; a front view, about as wide as it is tall, one
  // above the other, so it is drawn as big as a side view.
  const ratio = (x1 - x0) / (y1 - y0)
  const wide = ratio > (view === 'front' ? 0.7 : 1.3)
  const seen = figure.front ? ` from the ${view}` : ''
  const toggle =
    'min-h-11 rounded-xl border-2 border-[var(--line)] px-3 text-sm font-bold text-[var(--ink)] aria-pressed:border-[var(--ink)] aria-pressed:bg-[var(--line)]'
  return (
    <div ref={box} className="flex flex-col gap-2">
      {still ? (
        <div className={'grid gap-3 ' + (wide ? 'grid-cols-1' : 'grid-cols-2')}>
          {[first, last].map((text, i) => (
            <figure key={i} className="m-0 flex flex-col gap-1">
              <Drawing
                figure={figure}
                t={i}
                view={view}
                label={`${name}${seen}, ${i ? 'end' : 'start'}: ${text}`}
              />
              <figcaption className="text-sm text-[var(--slate)]">
                <b className="text-[var(--ink)]">{i ? 'End.' : 'Start.'}</b> {text}
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <Drawing
          figure={figure}
          t={t}
          view={view}
          label={`${name}${seen}, moving from: ${first}, to: ${last}`}
        />
      )}
      <div className="flex flex-wrap gap-2">
        {figure.front && !figure.front.only && (
          <div role="group" aria-label="Seen from" className="flex gap-2">
            {(['front', 'side'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={toggle}
              >
                {v === 'front' ? 'Front' : 'Side'}
              </button>
            ))}
          </div>
        )}
        <button
          type="button"
          aria-pressed={still}
          onClick={() => setStill((s) => !s)}
          className={toggle}
        >
          Start and end
        </button>
      </div>
    </div>
  )
}
