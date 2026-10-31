/** The server answers 451 to a visitor from outside the EU and EEA (ADR-0085). The page itself
 * then never loads, but a web app already open, or started from the installed app's cache,
 * only sees its API calls refused: any 451 shows the region page, with the server's reason,
 * instead of an error. */
export function watchRegion(show: (reason?: string) => void): void {
  const original = window.fetch.bind(window)
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const res = await original(...args)
    if (res.status === 451) {
      const body = (await res
        .clone()
        .json()
        .catch(() => ({}))) as { reason?: unknown }
      show(typeof body.reason === 'string' ? body.reason : undefined)
    }
    return res
  }
}
