import { expect, test } from 'vitest'
import { emptyWeek } from '../test/cardioWeek'
import { range, standing, zoneRows } from './cardioTotals'

test('what is left of a target, and over it is fine', () => {
  expect(standing(45)).toBe('45 min left') // nothing yet: all of the low end
  expect(standing(10)).toBe('10 min left')
  expect(standing(0)).toBe('on target') // inside the range, or over it: never a warning
  expect(standing(null)).toBeNull() // no target
  expect(range([45, 75])).toBe(' of 45–75')
  expect(range(null)).toBe('')
})

test('zone rows: heart rate where there was some, the kind picked where there was none', () => {
  const zones = emptyWeek({ zones: { zone2: 20, zone2_no_hr: 30, zone5: 2 } }).zones
  expect(zoneRows(zones)).toEqual([
    { label: 'Zone 2', minutes: 50, note: '30 without heart rate', measured: true },
    { label: 'Zone 5', minutes: 2, note: null, measured: true },
  ])
  expect(zoneRows(emptyWeek().zones)).toEqual([])
  const typed = zoneRows(emptyWeek({ zones: { zone2_no_hr: 30 } }).zones)
  expect(typed).toEqual([
    { label: 'Zone 2', minutes: 30, note: '30 without heart rate', measured: false },
  ])
})
