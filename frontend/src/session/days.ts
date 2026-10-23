/** The ISO day ``n`` days from ``iso``, counted on the calendar (no time zone can shift it). */
export function shift(iso: string, n: number): string {
  const at = new Date(`${iso}T12:00:00Z`)
  at.setUTCDate(at.getUTCDate() + n)
  return at.toISOString().slice(0, 10)
}
