import type { Exercise } from '../api'

export function Ladders({ exercises }: { exercises: Exercise[] }) {
  return (
    <div className="ladders">
      {exercises.map((e) => (
        <section key={e.slug} className="ladder" aria-label={e.name}>
          <h3>{e.name}</h3>
          <ol>
            {e.ladder.map((step, i) => {
              const state = i < e.current_step ? 'done' : i === e.current_step ? 'now' : 'next'
              return (
                <li key={step} className={`ladder-step is-${state}`}>
                  <span className="ladder-dot" aria-hidden="true" />
                  <span className="ladder-text">
                    {step}
                    {state === 'now' && <span className="ladder-now"> (current)</span>}
                  </span>
                </li>
              )
            })}
          </ol>
        </section>
      ))}
    </div>
  )
}
