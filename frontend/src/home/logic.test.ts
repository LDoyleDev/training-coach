import { expect, test } from 'vitest'
import { ago, day } from './logic'

test('a local ISO date reads as a short day', () => {
  expect(day('2026-09-01')).toMatch(/Tue 1 Sept?/)
})

test('days since read naturally', () => {
  expect(ago(0)).toBe('today')
  expect(ago(1)).toBe('1 day ago')
  expect(ago(40)).toBe('40 days ago')
  expect(ago(1200)).toBe('1,200 days ago')
})
