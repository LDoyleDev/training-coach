const colours = (on: boolean) =>
  on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]'

/** A one-tap answer, pressed when it's the one chosen (as Account's switches). */
export const choice = (on: boolean) =>
  'min-h-14 w-full rounded-xl border-2 px-4 py-2 text-left text-lg font-bold ' + colours(on)

/** A smaller one, a few to a row, for changes on the plan screen. */
export const tight = (on: boolean) =>
  'min-h-11 w-full rounded-xl border-2 px-1 text-center font-bold ' + colours(on)
