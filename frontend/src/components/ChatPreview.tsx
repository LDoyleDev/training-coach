type Msg = { from: 'coach' | 'me'; time: string; lines: string[]; buttons?: string[] }

const MESSAGES: Msg[] = [
  {
    from: 'coach',
    time: '07:30',
    lines: [
      'Good morning. Today is Torso + neck, about 60 minutes.',
      'Pull-ups: 4 sets, aim 8 / 8 / 7 / 6',
      'Dips: 3 sets, aim 12 / 11 / 10',
      'Then rows, push-ups, pike push-ups, reverse flys and neck work.',
    ],
    buttons: ['Start', 'Rest today'],
  },
  {
    from: 'me',
    time: '18:42',
    lines: ['Voice note, 0:24', '“Pull-ups 8 8 7 6, dips 12 11 10, rows 15 each side…”'],
  },
  {
    from: 'coach',
    time: '18:42',
    lines: [
      'Got it: 8 exercises, 23 sets. Save?',
      'Pull-ups 8 / 8 / 7 / 6, dips 12 / 11 / 10, rows 15 / 15 / 14 each side…',
    ],
    buttons: ['Save', 'Edit'],
  },
  {
    from: 'coach',
    time: '18:43',
    lines: [
      'Saved. New best on dips.',
      'Push-ups hit the top of the range two sessions in a row. Move up to feet elevated?',
    ],
    buttons: ['Move up', 'Not yet'],
  },
]

export function ChatPreview() {
  return (
    <div className="chat" role="img" aria-label="Example Telegram conversation with the coach">
      {MESSAGES.map((m, i) => (
        <div key={i} className={`bubble from-${m.from}`}>
          {m.lines.map((l, j) => (
            <p key={j}>{l}</p>
          ))}
          {m.buttons && (
            <div className="bubble-buttons">
              {m.buttons.map((b) => (
                <span key={b}>{b}</span>
              ))}
            </div>
          )}
          <span className="bubble-time">{m.time}</span>
        </div>
      ))}
    </div>
  )
}
