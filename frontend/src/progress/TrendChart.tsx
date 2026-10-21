import type { Standing } from '../api'
import { BOX, WEEKS, chart, shortDay } from './chart'
import { amount } from './logic'

/** One exercise's best set per session over the last six weeks: dates along the bottom, the
 * range up the side, and a dashed line where it moved up a step (fewer reps, harder step). */
export default function TrendChart({ standing, today }: { standing: Standing; today: Date }) {
  const found = chart(standing.trend, today)
  if (!found)
    return <p className="m-0 text-sm text-[var(--slate)]">No sessions in the last {WEEKS} weeks.</p>
  const show = (v: number) => amount(standing, v)
  const sessions = found.dots.length
  const label =
    `Best set per session, last ${WEEKS} weeks: ${sessions} ${sessions === 1 ? 'session' : 'sessions'}` +
    `, from ${show(found.dots[0].point.best)} to ${show(found.dots[sessions - 1].point.best)}` +
    found.moves.map((m) => `, moved up to step ${m.step}`).join('')
  const bottom = BOX.height - BOX.bottom
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
        </g>
        {found.moves.map((m) => (
          <g key={m.x}>
            <line
              x1={m.x}
              x2={m.x}
              y1={BOX.top}
              y2={bottom}
              stroke="var(--bell-ink)"
              strokeDasharray="3 3"
            />
            <text x={m.x + 3} y={BOX.top - 4} fontSize="10" fill="var(--bell-ink)">
              Step {m.step}
            </text>
          </g>
        ))}
        {sessions > 1 && (
          <polyline
            points={found.line}
            fill="none"
            stroke="var(--bell-ink)"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        )}
        {found.dots.map((d) => (
          <circle key={d.point.day + d.x} cx={d.x} cy={d.y} r="3.5" fill="var(--bell-ink)" />
        ))}
      </svg>
    </figure>
  )
}
