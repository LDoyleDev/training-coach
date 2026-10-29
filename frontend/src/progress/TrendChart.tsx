import type { Standing } from '../api'
import {
  BOX,
  PAD,
  STRIP,
  WEEKS,
  chart,
  fitSize,
  kindFor,
  local,
  shortDay,
  strip,
  type Period,
} from './chart'
import { amount } from './logic'

/** Arrows in text style: without the selector some fonts draw them as coloured emoji, and the
 * chart's changes must never be told by colour. */
const asText = (label: string) => label.replace(/[↑↓]/g, (arrow) => `${arrow}︎`)

/** One exercise's best set per session over the last six weeks: dates along the bottom, the
 * range up the side. Each ladder step is its own period (ADR-0072): the line breaks at a
 * change, the periods alternate plain and faintly tinted, and each change is labelled with its
 * step and an arrow, so fewer reps after a step up reads as the method working. On a loaded
 * step each weight is a period instead, and a strip under the chart shows the weight. */
export default function TrendChart({ standing, today }: { standing: Standing; today: Date }) {
  const kind = kindFor(standing.trend)
  const found = chart(standing.trend, today, kind)
  if (!found)
    return <p className="m-0 text-sm text-[var(--slate)]">No sessions in the last {WEEKS} weeks.</p>
  const show = (v: number) => amount(standing, v)
  const sessions = found.dots.length
  const change = (p: Period, before: Period) =>
    `. Moved ${p.move} to ${kind.words(p.key)} on ${shortDay(local(p.dots[0].point.day))}` +
    `; best ${show(before.dots.at(-1)!.point.best)} to ${show(p.dots[0].point.best)}`
  const label =
    `Best set per session, last ${WEEKS} weeks: ${sessions} ${sessions === 1 ? 'session' : 'sessions'}` +
    `, from ${show(found.dots[0].point.best)} to ${show(found.dots[sessions - 1].point.best)}` +
    found.periods
      .slice(1)
      .map((p, i) => change(p, found.periods[i]))
      .join('')
  const bottom = BOX.height - BOX.bottom
  const weights = strip(found.dots)
  // Both ends of the strip's scale, with their unit.
  const scale = weights ? [`${weights.high} kg`, `${weights.low} kg`] : []
  return (
    <figure className="m-0 flex flex-col gap-1">
      <figcaption className="text-sm text-[var(--slate)]">
        Best set per session · last {WEEKS} weeks
      </figcaption>
      <svg
        viewBox={`0 0 ${BOX.width} ${BOX.height}`}
        role="img"
        aria-label={label}
        className="w-full"
      >
        {found.periods.map(
          (p, i) =>
            p.tinted && (
              <rect
                key={i}
                data-period-tint=""
                x={p.from}
                y={BOX.top}
                width={p.to - p.from}
                height={bottom - BOX.top}
                fill="var(--period-tint)"
              />
            ),
        )}
        {found.weeks.map((x) => (
          <line key={x} x1={x} x2={x} y1={BOX.top} y2={bottom} stroke="var(--line)" />
        ))}
        <line
          x1={BOX.left}
          x2={BOX.width - BOX.right}
          y1={bottom}
          y2={bottom}
          stroke="var(--slate)"
        />
        <g fontSize="10" fill="var(--slate)">
          <text x={BOX.left - 4} y={BOX.top + 4} textAnchor="end">
            {show(found.high)}
          </text>
          {found.low !== found.high && (
            <text x={BOX.left - 4} y={bottom} textAnchor="end">
              {show(found.low)}
            </text>
          )}
          <text x={BOX.left} y={BOX.height - 4}>
            {shortDay(found.start)}
          </text>
          <text x={BOX.width - BOX.right} y={BOX.height - 4} textAnchor="end">
            Today
          </text>
          {found.periods.map(
            (p, i) =>
              p.label !== null && (
                <text
                  key={i}
                  x={p.from + PAD}
                  y={BOX.top - 5}
                  fill="var(--ink)"
                  style={{ fontVariantEmoji: 'text' }}
                >
                  {asText(p.label)}
                </text>
              ),
          )}
        </g>
        {found.periods.map(
          (p, i) =>
            p.line !== '' && (
              <polyline
                key={i}
                points={p.line}
                fill="none"
                stroke="var(--bell-ink)"
                strokeWidth="2"
                strokeLinejoin="round"
              />
            ),
        )}
        {found.dots.map((d) => (
          <circle key={d.point.day + d.x} cx={d.x} cy={d.y} r="3.5" fill="var(--bell-ink)" />
        ))}
      </svg>
      {weights && (
        <svg
          viewBox={`0 0 ${BOX.width} ${STRIP.height}`}
          role="img"
          aria-label={
            weights.low === weights.high
              ? `Weight: ${weights.low} kg every session`
              : `Weight per session, from ${weights.low} kg to ${weights.high} kg`
          }
          className="w-full"
        >
          <g fontSize={fitSize(scale, BOX.left - 4)} fill="var(--slate)">
            <text x={BOX.left - 4} y={STRIP.top + 4} textAnchor="end">
              {scale[0]}
            </text>
            {weights.low !== weights.high && (
              <text x={BOX.left - 4} y={STRIP.height - STRIP.bottom} textAnchor="end">
                {scale[1]}
              </text>
            )}
          </g>
          <path d={weights.path} fill="none" stroke="var(--ink)" strokeWidth="1.5" />
        </svg>
      )}
    </figure>
  )
}
