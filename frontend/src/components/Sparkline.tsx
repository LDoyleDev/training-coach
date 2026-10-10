import { trend } from './trend'

/** A small trend line (Progress, Tests, Body); nothing until there are two values. Higher is
 * up, whatever "better" means for the value: bodyweight or waist going down draws down. */
export default function Sparkline({ values, label }: { values: number[]; label: string }) {
  const points = trend(values)
  if (!points) return null
  return (
    <svg
      width="120"
      height="32"
      viewBox="0 0 120 32"
      role="img"
      aria-label={label}
      className="shrink-0"
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--bell-ink)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}
