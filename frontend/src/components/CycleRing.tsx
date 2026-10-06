import type { Session } from '../api'

type Props = {
  sessions: Session[]
  selected: string | null
  onSelect: (slug: string) => void
}

const SIZE = 320
const C = SIZE / 2
const R = 122
const STROKE = 30
const GAP_DEG = 5

function polar(deg: number, r = R) {
  const rad = ((deg - 90) * Math.PI) / 180
  return { x: C + r * Math.cos(rad), y: C + r * Math.sin(rad) }
}

function arc(start: number, end: number) {
  const a = polar(start)
  const b = polar(end)
  const large = end - start > 180 ? 1 : 0
  return `M ${a.x} ${a.y} A ${R} ${R} 0 ${large} 1 ${b.x} ${b.y}`
}

/** The week as a loop: seven arcs in queue order, starting at the top. */
export function CycleRing({ sessions, selected, onSelect }: Props) {
  const step = 360 / sessions.length
  const start = polar(0, R + STROKE / 2 + 12)
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="cycle"
      role="group"
      aria-label="The seven sessions as a repeating cycle"
    >
      {sessions.map((s, i) => {
        const a0 = i * step + GAP_DEG / 2
        const a1 = (i + 1) * step - GAP_DEG / 2
        const mid = polar((a0 + a1) / 2)
        const isSel = selected === s.slug
        return (
          <g
            key={s.slug}
            className={`cycle-seg cycle-${s.type}${isSel ? ' is-selected' : ''}`}
            style={{ animationDelay: `${120 + i * 90}ms` }}
          >
            <path d={arc(a0, a1)} pathLength={1} strokeWidth={STROKE} fill="none" />
            <text x={mid.x} y={mid.y} dy="0.35em" textAnchor="middle" className="cycle-num">
              {i + 1}
            </text>
            <path
              d={arc(a0, a1)}
              strokeWidth={STROKE + 10}
              fill="none"
              className="cycle-hit"
              tabIndex={0}
              role="button"
              aria-label={`${i + 1}. ${s.name}`}
              aria-pressed={isSel}
              onClick={() => onSelect(s.slug)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(s.slug)
                }
              }}
            />
          </g>
        )
      })}
      <circle cx={start.x} cy={start.y} r={5} className="cycle-start" />
      <text x={C} y={C - 6} textAnchor="middle" className="cycle-center-big">
        {sessions.length}
      </text>
      <text x={C} y={C + 22} textAnchor="middle" className="cycle-center-small">
        sessions, one loop
      </text>
    </svg>
  )
}
