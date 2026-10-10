type Props = {
  volume: { group: string; sets: number }[]
  min: number
  max: number
}

const label = (g: string) => g.charAt(0).toUpperCase() + g.slice(1)

export function VolumeChart({ volume, min, max }: Props) {
  const scale = Math.max(max + 4, ...volume.map((v) => v.sets))
  const pct = (n: number) => `${(n / scale) * 100}%`
  return (
    <figure className="volume">
      <div className="volume-axis" aria-hidden="true">
        <span style={{ left: pct(min) }}>{min}</span>
        <span style={{ left: pct(max) }}>{max}</span>
      </div>
      <ul className="volume-rows">
        {volume.map((v) => {
          const inRange = v.sets >= min && v.sets <= max
          return (
            <li key={v.group} className="volume-row">
              <span className="volume-label">{label(v.group)}</span>
              <span className="volume-track">
                <span
                  className="volume-band"
                  style={{ left: pct(min), width: pct(max - min) }}
                  aria-hidden="true"
                />
                <span
                  className={`volume-bar${inRange ? ' in-range' : ''}`}
                  style={{ width: pct(v.sets) }}
                  aria-hidden="true"
                />
              </span>
              <span className="volume-value num">{v.sets}</span>
            </li>
          )
        })}
      </ul>
      <figcaption>
        Shaded: the common {min}–{max} hard sets a week guideline. Small muscles like the neck,
        calves and shins sit below it on purpose.
      </figcaption>
    </figure>
  )
}
