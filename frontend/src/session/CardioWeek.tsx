import { range, standing, zoneRows, type CardioWeekView } from './cardioTotals'

const percent = (part: number, whole: number) =>
  whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0

function Line({
  label,
  done,
  target,
  left,
}: {
  label: string
  done: number
  target: readonly number[] | null
  left: number | null
}) {
  const where = standing(left)
  return (
    <div className="flex flex-col gap-1">
      <p className="m-0">
        {label}: <span className="font-bold tabular-nums">{done}</span>
        {range(target)} min{where ? ` · ${where}` : ''}
      </p>
      {target && (
        <div
          role="meter"
          aria-label={`${label} in the last 7 days`}
          aria-valuemin={0}
          aria-valuemax={target[0]}
          aria-valuenow={Math.min(done, target[0])}
          className="h-3 overflow-hidden rounded-full bg-[var(--line)]"
        >
          <div
            className="h-full bg-[var(--bell)]"
            style={{ width: `${percent(done, target[0])}%` }}
          />
        </div>
      )}
    </div>
  )
}

/** The last 7 days of cardio (ADR-0077, ADR-0079): all of it and zone 2 against the targets,
 * then the minutes in each zone. Every row says its zone and minutes in words; the bars only
 * repeat them. */
export default function CardioWeek({ week }: { week: CardioWeekView }) {
  const rows = zoneRows(week.zones)
  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="m-0 font-bold">Last 7 days</p>
      <Line label="Cardio" done={week.total} target={week.total_target} left={week.total_left} />
      <Line label="Zone 2" done={week.zone2} target={week.zone2_target} left={week.zone2_left} />
      {rows.length > 0 && (
        <ul
          aria-label="Cardio minutes by heart-rate zone"
          className="m-0 flex list-none flex-col gap-2 p-0"
        >
          {rows.map((r) => (
            <li key={r.label} className="flex flex-col gap-1">
              <span className="flex justify-between gap-3">
                <span>
                  {r.label}
                  {r.note && <span className="text-[var(--slate)]"> · {r.note}</span>}
                </span>
                <span className="font-bold whitespace-nowrap tabular-nums">{r.minutes} min</span>
              </span>
              <span
                className="h-2 overflow-hidden rounded-full bg-[var(--line)]"
                aria-hidden="true"
              >
                <span
                  className={`block h-full ${r.measured ? 'bg-[var(--bell)]' : 'bg-[var(--slate)]'}`}
                  style={{ width: `${percent(r.minutes, week.total)}%` }}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
