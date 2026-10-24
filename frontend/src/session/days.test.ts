import { expect, test } from 'vitest'
import { details, shift } from './days'

test('steps days on the calendar, across months, years and clock changes', () => {
  expect(shift('2026-10-23', -1)).toBe('2026-10-22')
  expect(shift('2026-11-01', -1)).toBe('2026-10-31')
  expect(shift('2026-12-31', 1)).toBe('2027-01-01')
  expect(shift('2026-10-25', 1)).toBe('2026-10-26') // the clocks go back in Berlin that night
  expect(shift('2027-03-28', -1)).toBe('2027-03-27') // and forward
})

test('cardio details show only what was given', () => {
  const none = { effort: null, distance_m: null, pace_s_per_km: null, avg_hr: null, max_hr: null }
  expect(details({ ...none, effort: 6 })).toBe('Effort 6/10')
  expect(details({ ...none, distance_m: 5000, pace_s_per_km: 305, avg_hr: 150, max_hr: 172 })).toBe(
    '5.00 km · 5:05/km · avg 150 bpm · max 172',
  )
  expect(details(none)).toBe('')
  const ride = { ...none, distance_m: 36400, pace_s_per_km: 148 }
  expect(details(ride, 'bike')).toBe('36.40 km · 24.3 km/h') // a ride: speed, not pace
  expect(details(ride, 'run')).toBe('36.40 km · 2:28/km')
})
