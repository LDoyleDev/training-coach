/** Where to go after signing in: ?next=, if it is a path on this site, else Today. */
export function nextPage(search: string): string {
  const next = new URLSearchParams(search).get('next') ?? ''
  const local = next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')
  return local ? next : '/'
}
