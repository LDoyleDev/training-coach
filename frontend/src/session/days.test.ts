import { expect, test } from 'vitest'
import { shift } from './days'

test('steps days on the calendar, across months, years and clock changes', () => {
  expect(shift('2026-10-23', -1)).toBe('2026-10-22')
  expect(shift('2026-11-01', -1)).toBe('2026-10-31')
  expect(shift('2026-12-31', 1)).toBe('2027-01-01')
  expect(shift('2026-10-25', 1)).toBe('2026-10-26') // the clocks go back in Berlin that night
  expect(shift('2027-03-28', -1)).toBe('2027-03-27') // and forward
})
