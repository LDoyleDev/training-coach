/** Minutes as hours and minutes: 440 -> "7 h 20 min". */
export function hours(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${h} h ${m} min`
  return h ? `${h} h` : `${m} min`
}
