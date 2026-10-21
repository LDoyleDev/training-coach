import { useEffect, useId, useRef, useState } from 'react'
import { blend, progress } from './body'
import { FIGURES, type Figure as Data } from './poses'
import { ORDER, shapes, type Shape, type Tone } from './shapes'

const TONES: readonly Tone[] = ['near', 'far', 'prop', 'bell']

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function Drawn({ shape, id }: { shape: Shape; id: string }) {
  const line = {
    stroke: `var(--fig-${'tone' in shape ? shape.tone : 'prop'}-line)`,
    strokeWidth: 1,
  }
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
      <circle
        cx={shape.c[0]}
        cy={shape.c[1]}
        r={shape.r}
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

/** One drawing of ``figure``, ``t`` of the way from its start (0) to its end (1). */
function Drawing({ figure, t, label }: { figure: Data; t: number; label: string }) {
  const id = 'fig' + useId().replace(/[^a-zA-Z0-9]/g, '')
  const [x0, x1, y0, y1] = figure.view
  const pose = t <= 0 ? figure.start : t >= 1 ? figure.end : blend(figure.start, figure.end, t)
  return (
    <svg
      viewBox={`${x0} ${-y1} ${x1 - x0} ${y1 - y0}`}
      role="img"
      aria-label={label}
      className="block max-h-72 w-full"
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
      <line
        x1={x0}
        x2={x1}
        y1={0}
        y2={0}
        stroke="var(--fig-floor)"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      {shapes(pose, figure.props, figure.order ?? ORDER).map((shape, i) => (
        <Drawn key={i} shape={shape} id={id} />
      ))}
    </svg>
  )
}

/** One still of an exercise's figure, ``t`` from its start (0) to its end (1); nothing for a
 * slug without a figure. */
export function FigureAt({ slug, t, label }: { slug: string; t: number; label: string }) {
  const figure: Data | undefined = FIGURES[slug]
  return figure ? <Drawing figure={figure} t={t} label={label} /> : null
}

/** An exercise's mannequin (ADR-0063), moving from its start to its end and back, or the two
 * positions side by side. Starts still for people who ask for less motion; nothing for a slug
 * without a figure. */
export default function Figure({ slug, name }: { slug: string; name: string }) {
  const figure: Data | undefined = FIGURES[slug]
  const [still, setStill] = useState(reducedMotion)
  const [t, setT] = useState(0)
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
  const [x0, x1, y0, y1] = figure.view
  const wide = (x1 - x0) / (y1 - y0) > 1.3
  return (
    <div ref={box} className="flex flex-col gap-2">
      {still ? (
        <div className={'grid gap-3 ' + (wide ? 'grid-cols-1' : 'grid-cols-2')}>
          {[first, last].map((text, i) => (
            <figure key={i} className="m-0 flex flex-col gap-1">
              <Drawing figure={figure} t={i} label={`${name}, ${i ? 'end' : 'start'}: ${text}`} />
              <figcaption className="text-sm text-[var(--slate)]">
                <b className="text-[var(--ink)]">{i ? 'End.' : 'Start.'}</b> {text}
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <Drawing figure={figure} t={t} label={`${name}, moving from: ${first}, to: ${last}`} />
      )}
      <button
        type="button"
        aria-pressed={still}
        onClick={() => setStill((s) => !s)}
        className="min-h-11 self-start rounded-xl border-2 border-[var(--line)] px-3 text-sm font-bold text-[var(--ink)] aria-pressed:border-[var(--ink)]"
      >
        Start and end
      </button>
    </div>
  )
}
