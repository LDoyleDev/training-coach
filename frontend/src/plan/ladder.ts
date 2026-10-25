import type { Moved, Standing } from '../api'

/** Where a "Ready to move up" goes: that exercise's ladder on the Plan page (ADR-0075). */
export function moveHref(slug: string): string {
  return `/plan?move=${encodeURIComponent(slug)}`
}

/** A "Ready to move up" link that looks and taps like a button (44 px tall). */
export const moveButton =
  'inline-flex min-h-11 items-center self-start rounded-xl border-2 border-[var(--bell-ink)] px-3 font-bold text-[var(--bell-ink)] no-underline'

/** The exercise a link asked for, from `?move=<slug>`. */
export function wanted(search: string): string | null {
  return new URLSearchParams(search).get('move')
}

type Rung = Standing['ladder'][number]

/** The next step the kit allows, if there is one: Move up skips locked steps (ADR-0071). */
export function nextRung(s: Standing): Rung | null {
  const at = s.ladder.findIndex((r) => r.id === s.step_id)
  if (at < 0) return null
  return s.ladder.slice(at + 1).find((r) => r.missing.length === 0) ?? null
}

/** A locked step in words, never colour alone: "needs a 16 kg kettlebell". Null when open. */
export function needs(r: Rung): string | null {
  return r.missing.length > 0 ? `needs ${r.missing.join(' and ')}` : null
}

/** "Top for your kit" when the steps above are all locked, else the plain top or nothing. */
export function topLabel(s: Standing): string | null {
  if (s.unlock) return 'Top for your kit'
  return s.status === 'top_of_ladder' ? 'Top of the ladder' : null
}

export const WAITS =
  'Moving up waits for the hypertrophy block: this is a strength block. ' +
  'You can still choose a level by hand.'

export function confirmText(step: string): string {
  return `Targets for ${step} start fresh from its own history.`
}

/** What a press did, in plain words, as the bot says it. */
export function said(m: Moved): string {
  const { exercise, step } = m
  switch (m.outcome) {
    case 'moved':
      return `Moved up: ${exercise} is now ${step}. Targets start again at the bottom of the range.`
    case 'already_moved':
      return `${exercise} has already moved on since this page loaded. Here is where it is now.`
    case 'not_ready':
      return `${exercise} doesn't meet the rule any more. Keep going.`
    case 'no_next_step':
      return `${exercise} is on the last step in your plan.`
    case 'strength_block':
      return `${exercise} waits for the hypertrophy block: this is a strength block.`
    case 'stayed':
      return `Staying on ${step}. You'll be asked again after your next session at the top of the range.`
    case 'level_set':
      return `${exercise} is now on ${step}. ${confirmText(step ?? 'it')}${m.warning ? ` ${m.warning}` : ''}`
    case 'same_level':
      return `${exercise} is already on ${step}.`
  }
}
