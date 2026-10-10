/** The pages sign-in may return to. Only these: ?next= is user input, and matching a fixed
 * list (rather than checking the string's shape) can't be tricked into leaving the site,
 * for example by a tab or newline the URL parser strips ("/\t/evil.example"). */
const PAGES = ['/session', '/progress', '/plan', '/tests', '/body', '/readiness', '/account']

/** Where to go after signing in: ?next= if it names one of the app's pages, else Today. */
export function nextPage(search: string): string {
  const next = new URLSearchParams(search).get('next') ?? ''
  return PAGES.find((page) => page === next) ?? '/'
}
