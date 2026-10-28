import { expect, test } from 'vitest'
import type { ItemLevel } from '../api'
import { levelNote, nearby } from './levels'

const rung = (id: number) => ({ id, name: `Step ${id}`, cue: null, missing: [] })
const ladder = [1, 2, 3, 4, 5].map(rung)
const at = (step_id: number): ItemLevel => ({ step_id, for_today: false, ladder })

test('one level down and one up are shown first', () => {
  expect(nearby(at(3)).map((r) => r.id)).toEqual([2, 3, 4])
  expect(nearby(at(1)).map((r) => r.id)).toEqual([1, 2])
  expect(nearby(at(5)).map((r) => r.id)).toEqual([4, 5])
  expect(nearby(at(9)).map((r) => r.id)).toEqual([1, 2, 3, 4, 5]) // not on it: every level
})

test('the note says what changed, for today or from now on, with any kit warning', () => {
  expect(levelNote('Kettlebell swing', 'Two-hand, 16 kg', 'today', null)).toBe(
    'Kettlebell swing: Two-hand, 16 kg for today. Your level stays as it was. ' +
      'Targets for Two-hand, 16 kg start fresh from its own history.',
  )
  expect(
    levelNote(
      'Kettlebell swing',
      'Two-hand, 16 kg',
      'from_now_on',
      'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.',
    ),
  ).toBe(
    'Kettlebell swing is now on Two-hand, 16 kg, today and from now on. ' +
      'Targets for Two-hand, 16 kg start fresh from its own history. ' +
      'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.',
  )
})
