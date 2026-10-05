import { prescription, sessionSize, type Session } from '../api'

type Props = {
  sessions: Session[]
  open: string | null
  onToggle: (slug: string) => void
}

const TYPE_LABEL = { strength: 'Strength', conditioning: 'Conditioning', recovery: 'Recovery' }

export function SessionList({ sessions, open, onToggle }: Props) {
  return (
    <ol className="sessions">
      {sessions.map((s) => {
        const isOpen = open === s.slug
        const panel = `session-${s.slug}`
        return (
          <li key={s.slug} className={`session session-${s.type}`} id={`row-${s.slug}`}>
            <button
              type="button"
              className="session-head"
              aria-expanded={isOpen}
              aria-controls={panel}
              onClick={() => onToggle(s.slug)}
            >
              <span className="session-num" aria-hidden="true">
                {s.position + 1}
              </span>
              <span className="session-title">
                <span className="session-name">{s.name}</span>
                <span className="session-focus">{s.focus}</span>
              </span>
              <span className="session-meta">
                <span className="session-type">{TYPE_LABEL[s.type]}</span>
                <span className="session-size">{sessionSize(s)}</span>
              </span>
              <span className="session-chevron" aria-hidden="true" />
            </button>
            <div id={panel} className="session-body" hidden={!isOpen}>
              {s.optional && (
                <p className="session-note">
                  Optional: take a full rest day instead if you need it.
                </p>
              )}
              <table className="exercises">
                <thead>
                  <tr>
                    <th scope="col">Exercise</th>
                    <th scope="col">Work</th>
                    <th scope="col">Starting variation</th>
                  </tr>
                </thead>
                <tbody>
                  {s.exercises.map((e) => (
                    <tr key={e.slug}>
                      <th scope="row">{e.name}</th>
                      <td className="num">{prescription(e)}</td>
                      <td>{e.ladder[e.start_step]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
