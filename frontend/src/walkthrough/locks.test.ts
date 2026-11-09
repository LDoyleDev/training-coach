import { describe, expect, test } from 'vitest'
import cases from './lock-cases.json?raw'
import { AVOIDABLE, avoided, isOpen, missing, type Limits } from './locks'

// The same cases as backend/tests/domain/test_kit.py and test_locks.py.
const item = (kit: string, more: { kg?: number; min_kg?: number; resistance?: string } = {}) =>
  ({ kit, kg: null, min_kg: null, resistance: null, ...more }) as NonNullable<Limits['kit']>[number]
const KB8 = item('kettlebell', { kg: 8 })
const KB16 = item('kettlebell', { kg: 16 })
const BAR = item('pull-up bar')
const NOTHING: Limits = { kit: null, avoid: new Set() }

describe('kit (ADR-0071)', () => {
  test('an unlisted kit locks nothing', () => {
    expect(missing(null, ['kettlebell:16', 'pull-up bar'])).toEqual([])
  })

  test('a kettlebell must be that exact weight', () => {
    expect(missing([KB8], ['kettlebell:8'])).toEqual([])
    expect(missing([KB8], ['kettlebell:16'])).toEqual(['kettlebell:16'])
    expect(missing([KB16], ['kettlebell:8'])).toEqual(['kettlebell:8'])
    expect(missing([KB8, KB16], ['kettlebell:8', 'kettlebell:16'])).toEqual([])
    expect(missing([item('kettlebell')], ['kettlebell:8'])).toEqual(['kettlebell:8'])
  })

  test('dumbbells: fixed pairs and adjustable ranges', () => {
    const pair = item('dumbbells', { kg: 12 })
    const adjustable = item('dumbbells', { kg: 24, min_kg: 2 })
    expect(missing([pair], ['dumbbells:12'])).toEqual([])
    expect(missing([pair], ['dumbbells:14'])).toEqual(['dumbbells:14'])
    expect(missing([adjustable], ['dumbbells:14'])).toEqual([])
    expect(missing([adjustable], ['dumbbells:30'])).toEqual(['dumbbells:30'])
    expect(missing([adjustable], ['dumbbells:1'])).toEqual(['dumbbells:1'])
    expect(missing([pair], ['dumbbells'])).toEqual([]) // any dumbbells
  })

  test('a vest or backpack loads up to its weight', () => {
    const vest = item('backpack', { kg: 10 })
    expect(missing([vest], ['backpack'])).toEqual([])
    expect(missing([vest], ['backpack:10'])).toEqual([])
    expect(missing([vest], ['backpack:15'])).toEqual(['backpack:15'])
    expect(missing([], ['backpack'])).toEqual(['backpack'])
  })

  test('other kit is there or not', () => {
    const band = item('band', { resistance: 'light' })
    expect(missing([band, BAR], ['band', 'pull-up bar'])).toEqual([])
    expect(missing([band], ['band', 'pull-up bar'])).toEqual(['pull-up bar'])
  })

  test('a band step takes that strength or a stronger one', () => {
    const medium = item('band', { resistance: 'medium' })
    expect(missing([medium], ['band:light'])).toEqual([])
    expect(missing([medium], ['band:medium'])).toEqual([])
    expect(missing([medium], ['band:heavy'])).toEqual(['band:heavy'])
    expect(missing([item('mat')], ['band:light'])).toEqual(['band:light'])
    expect(missing([item('band')], ['band:light'])).toEqual(['band:light'])
  })
})

describe('marks (ADR-0083)', () => {
  test('five marks can be avoided and balance is not one', () => {
    expect(AVOIDABLE).toEqual(['floor', 'kneeling', 'impact', 'hanging', 'knees'])
  })

  test('a mark the person avoids locks the step; others lock nothing', () => {
    const offFloor: Limits = { kit: null, avoid: new Set(['floor']) }
    expect(avoided(['floor', 'balance'], offFloor.avoid)).toEqual(['floor'])
    expect(isOpen({ needs: [], marks: ['floor', 'balance'] }, offFloor)).toBe(false)
    expect(isOpen({ needs: [], marks: ['balance'] }, offFloor)).toBe(true)
    expect(
      isOpen({ needs: [], marks: ['floor'] }, { kit: null, avoid: new Set(['hanging']) }),
    ).toBe(true)
  })

  test('every avoidable mark, in order', () => {
    const every = new Set<string>(AVOIDABLE)
    const all = ['knees', 'balance', 'hanging', 'impact', 'kneeling', 'floor']
    expect(avoided(all, every)).toEqual(AVOIDABLE)
  })
})

test('kit and marks lock together, and nothing listed or avoided locks nothing', () => {
  const asks = { needs: ['kettlebell:16'], marks: ['floor', 'hanging'] }
  expect(isOpen(asks, NOTHING)).toBe(true)
  expect(isOpen(asks, { kit: [KB16], avoid: new Set() })).toBe(true)
  expect(isOpen(asks, { kit: [KB8], avoid: new Set() })).toBe(false)
  expect(isOpen(asks, { kit: [KB16], avoid: new Set(['floor']) })).toBe(false)
})

interface Case {
  case: string
  needs: string[]
  marks: string[]
  kit: NonNullable<Limits['kit']> | null
  avoid: string[]
  open: boolean
  missing: string[] // in words on the server; here only how many
  avoided: string[]
}

// The cases backend/tests/domain/test_lock_cases.py runs domain.locks against (Decided 19).
const SHARED = (JSON.parse(cases) as { cases: Case[] }).cases.map((c) => ({
  ...c,
  kit: c.kit?.map((i) => ({ kg: null, min_kg: null, resistance: null, ...i })) ?? null,
}))

test.each(SHARED)('shared case: $case', (c) => {
  const limits: Limits = { kit: c.kit, avoid: new Set(c.avoid) }
  expect(isOpen(c, limits)).toBe(c.open)
  expect(missing(c.kit, c.needs)).toHaveLength(c.missing.length)
  expect(avoided(c.marks, limits.avoid)).toEqual(c.avoided)
})

test('the shared cases are all there', () => {
  expect(SHARED.length).toBeGreaterThanOrEqual(26)
})
