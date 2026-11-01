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
/** Why a step is locked: the kit it lacks (ADR-0071) and what it asks that the person has
 * chosen to avoid, already in words (ADR-0083). */
type Lockable = Pick<Rung, 'missing' | 'avoided'>

/** The next open step, if there is one: Move up skips locked steps (ADR-0071, ADR-0083). */
export function nextRung(s: Standing): Rung | null {
  const at = s.ladder.findIndex((r) => r.id === s.step_id)
  if (at < 0) return null
  return s.ladder.slice(at + 1).find((r) => needs(r) === null) ?? null
}

/** A locked step in words, never colour alone: "needs a 16 kg kettlebell", "needs the floor —
 * you've chosen to keep off it". Null when open. */
export function needs(r: Lockable): string | null {
  const kit = r.missing.length > 0 ? [`needs ${r.missing.join(' and ')}`] : []
  const reasons = [...kit, ...r.avoided]
  return reasons.length > 0 ? reasons.join('; ') : null
}

/** A locked step as a sentence, as the server's warning says it: "Two-hand, 16 kg needs a 16 kg
 * kettlebell, not in your kit." Null when open. */
export function lockedText(step: string, r: Lockable): string | null {
  const kit = r.missing.length > 0 ? [`needs ${r.missing.join(' and ')}, not in your kit`] : []
  const reasons = [...kit, ...r.avoided]
  return reasons.length > 0 ? `${step} ${reasons.join('; ')}.` : null
}

/** Said on Plan when the step someone is on is one they've since chosen to avoid. Their level
 * never changes by itself: they pick (ADR-0083). */
export const AVOIDED_NOW = "You've chosen to avoid this; pick another step."

/** Whether the step someone is on asks something they've chosen to avoid. */
export function avoidedNow(s: Standing): boolean {
  return s.ladder.some((r) => r.id === s.step_id && r.avoided.length > 0)
}

/** "Top for your kit" when kit locks the steps above; "Top of your open steps" when the steps
 * above are all locked otherwise; the plain top; or nothing. */
export function topLabel(s: Standing): string | null {
  if (s.unlock) return 'Top for your kit'
  if (s.status !== 'top_of_ladder') return null
  const at = s.ladder.findIndex((r) => r.id === s.step_id)
  return at >= 0 && at < s.ladder.length - 1 ? 'Top of your open steps' : 'Top of the ladder'
}

/** Said where every harder step is locked, as the server says it on every surface (ADR-0083). */
export const NO_OPEN_STEP = 'no open step above this one'

type StepDown = NonNullable<Standing['step_down']>

/** The step-down suggestion in plain words (ADR-0084): what happened, then a question. At a
 * ladder's first step there is nothing below, so it names easier exercises if there are any. */
export function stepDownText(d: StepDown): string {
  const seen = 'The bottom of the range was out of reach twice.'
  if (d.below) return `${seen} Try the step below?`
  const easier =
    d.easier.length > 0
      ? ` An easier exercise for the same muscles might suit: ${d.easier.join(' or ')}.`
      : ''
  return `${seen} This is the first step of its ladder, so there's no step below.${easier}`
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
      return `${exercise} is on the last step in your plan, or the last one open to you.`
    case 'strength_block':
      return `${exercise} waits for the hypertrophy block: this is a strength block.`
    case 'stayed':
      return `Staying on ${step}. You'll be asked again after your next session at the top of the range.`
    case 'level_set':
      return `${exercise} is now on ${step}. ${confirmText(step ?? 'it')}${m.warning ? ` ${m.warning}` : ''}`
    case 'same_level':
      return `${exercise} is already on ${step}.`
    case 'stepped_down':
      return `${exercise} is now on ${step}. ${confirmText(step ?? 'it')}${m.warning ? ` ${m.warning}` : ''}`
    case 'no_step_below':
      return `${exercise} is on the first step it can go to: there's no step below.`
    case 'stayed_down':
      return `Staying on ${step}. You'll be asked again if the bottom of the range is out of reach in a later session.`
  }
}
