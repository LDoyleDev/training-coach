import { local, shortDay } from '../progress/chart'
import { FAT_BOX, fatChart, type FatPoint, type FatSeries } from './fatChart'

/** What the tape estimate is called wherever it shows (ADR-0076). */
export const ESTIMATE = 'estimate from waist and neck, ±4%'

const percent = (v: number) => `${v.toFixed(1)} %`

type Look = { name: string; colour: string; dashed: boolean }
const SCALE: Look = { name: 'Scale', colour: 'var(--fat-scale)', dashed: false }
const TAPE: Look = { name: 'Tape, ' + ESTIMATE, colour: 'var(--fat-tape)', dashed: true }

const describe = (look: Look, points: FatPoint[]) => {
  if (points.length === 0) return null
  const oldest = points[points.length - 1].value
  const newest = points[0].value
  const count = `${points.length} ${points.length === 1 ? 'day' : 'days'}`
  return points.length === 1
    ? `${look.name}: ${count}, ${percent(newest)}`
    : `${look.name}: ${count}, from ${percent(oldest)} to ${percent(newest)}`
}

/** The swatch beside a legend name: a bit of the series' own line and dot, so solid against
 * dashed and filled against hollow say which is which without colour. */
function Swatch({ look }: { look: Look }) {
  return (
    <svg width="28" height="12" viewBox="0 0 28 12" aria-hidden="true" className="shrink-0">
      <line
        x1="1"
        x2="27"
        y1="6"
        y2="6"
        stroke={look.colour}
        strokeWidth="2"
        strokeDasharray={look.dashed ? '5 3' : undefined}
      />
      <circle
        cx="14"
        cy="6"
        r="4"
        fill={look.dashed ? 'var(--paper)' : look.colour}
        stroke={look.colour}
        strokeWidth="2"
      />
    </svg>
  )
}

function Line({ series, look }: { series: FatSeries; look: Look }) {
  return (
    <g>
      {series.line !== '' && (
        <polyline
          points={series.line}
          fill="none"
          stroke={look.colour}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeDasharray={look.dashed ? '5 4' : undefined}
        />
      )}
      {series.dots.map((d) => (
        <g key={d.point.on}>
          <title>{`${shortDay(local(d.point.on))}: ${percent(d.point.value)} (${look.name.toLowerCase()})`}</title>
          <circle cx={d.x} cy={d.y} r="10" fill="transparent" />
          <circle
            cx={d.x}
            cy={d.y}
            r="4"
            fill={look.dashed ? 'var(--paper)' : look.colour}
            stroke={look.dashed ? look.colour : 'var(--paper)'}
            strokeWidth="2"
          />
        </g>
      ))}
    </g>
  )
}

/** Body fat on one % axis: the scale's readings as a solid line with filled dots and, when the
 * estimate is on, the tape estimate as a dashed line with hollow dots, named in words. Points
 * are newest first. Nothing when there are none. */
export default function BodyFatChart({ scale, tape }: { scale: FatPoint[]; tape: FatPoint[] }) {
  const found = fatChart(scale, tape)
  if (!found) return null
  const label = ['Body fat, %', describe(SCALE, scale), describe(TAPE, tape)]
    .filter(Boolean)
    .join('. ')
  const bottom = FAT_BOX.height - FAT_BOX.bottom
  const legend = (
    [
      [SCALE, scale],
      [TAPE, tape],
    ] as [Look, FatPoint[]][]
  ).filter(([, points]) => points.length > 0)
  const sameDay = found.start.getTime() === found.end.getTime()
  return (
    <figure className="m-0 flex flex-col gap-1">
      <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-sm">
        {legend.map(([look]) => (
          <li key={look.name} className="flex items-center gap-2">
            <Swatch look={look} />
            <span>{look.name}</span>
          </li>
        ))}
      </ul>
      <svg
        viewBox={`0 0 ${FAT_BOX.width} ${FAT_BOX.height}`}
        role="img"
        aria-label={label}
        className="w-full"
      >
        <line
          x1={FAT_BOX.left}
          x2={FAT_BOX.width - FAT_BOX.right}
          y1={FAT_BOX.top}
          y2={FAT_BOX.top}
          stroke="var(--line)"
        />
        <line
          x1={FAT_BOX.left}
          x2={FAT_BOX.width - FAT_BOX.right}
          y1={bottom}
          y2={bottom}
          stroke="var(--slate)"
        />
        <g fontSize="10" fill="var(--slate)">
          <text x={FAT_BOX.left - 4} y={FAT_BOX.top + 4} textAnchor="end">
            {found.high}%
          </text>
          <text x={FAT_BOX.left - 4} y={bottom} textAnchor="end">
            {found.low}%
          </text>
          {sameDay ? (
            <text
              x={(FAT_BOX.left + FAT_BOX.width - FAT_BOX.right) / 2}
              y={FAT_BOX.height - 4}
              textAnchor="middle"
            >
              {shortDay(found.start)}
            </text>
          ) : (
            <>
              <text x={FAT_BOX.left} y={FAT_BOX.height - 4}>
                {shortDay(found.start)}
              </text>
              <text x={FAT_BOX.width - FAT_BOX.right} y={FAT_BOX.height - 4} textAnchor="end">
                {shortDay(found.end)}
              </text>
            </>
          )}
        </g>
        <Line series={found.tape} look={TAPE} />
        <Line series={found.scale} look={SCALE} />
      </svg>
    </figure>
  )
}
