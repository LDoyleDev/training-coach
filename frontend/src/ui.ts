/**
 * The shared look of actions and containers, as Tailwind classes. Every page uses these
 * instead of its own copy, so a button looks like a button everywhere (UX plan, part 1).
 * Plain <button>s already get an outlined look from index.css; these are for the rest.
 */

/** A section on a page: a light card with a border. */
export const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'

/** The one main action on a screen: full width, filled. */
export const primary =
  'min-h-14 w-full rounded-2xl border-0 bg-[var(--bell-ink)] px-4 text-lg font-bold text-[var(--chalk)] disabled:opacity-60'

/** A main action that sits inline: filled, as wide as its words. */
export const primaryInline =
  'min-h-11 rounded-xl border-0 bg-[var(--bell-ink)] px-4 font-bold text-[var(--chalk)] disabled:opacity-60'

/** Any other action: outlined. */
export const secondary =
  'min-h-11 rounded-xl border-2 border-[var(--ink)] px-4 font-bold text-[var(--ink)]'

/** A smaller outlined action, for lists and rows. */
export const small =
  'min-h-11 rounded-xl border-2 border-[var(--ink)] px-3 font-bold text-[var(--ink)]'

/** Something that can't be undone: outlined in the warning colour. */
export const danger =
  'min-h-11 rounded-xl border-2 border-[var(--bell-ink)] px-4 font-bold text-[var(--bell-ink)] disabled:opacity-50'

/** A row of actions that wraps on a phone. */
export const actions = 'flex flex-wrap gap-2'
