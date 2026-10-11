/** "Sun 11 Oct" for a local ISO date, without a time zone shifting the day. */
export function day(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

/** "today", "1 day ago", "40 days ago". */
export function ago(days: number): string {
  if (days <= 0) return 'today'
  return `${days.toLocaleString('en-GB')} ${days === 1 ? 'day' : 'days'} ago`
}
