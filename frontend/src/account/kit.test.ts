import { expect, test } from 'vitest'
import { label } from './kit'

test('an item held in memory is labelled as the server labels it', () => {
  const item = (more: object) => ({ kit: 'kettlebell' as const, note: '', ...more })
  expect(label(item({ kg: 16 }), 'kettlebell')).toBe('16 kg kettlebell')
  expect(label({ kit: 'dumbbells', kg: 24, min_kg: 2, note: '' }, 'dumbbells')).toBe(
    'adjustable dumbbells, 2-24 kg',
  )
  expect(label({ kit: 'dumbbells', kg: 12, note: '' }, 'dumbbells')).toBe('12 kg dumbbells')
  expect(label({ kit: 'backpack', kg: 10, note: '' }, 'weighted vest or backpack')).toBe(
    'weighted vest or backpack, up to 10 kg',
  )
  expect(label({ kit: 'band', resistance: 'light', note: '' }, 'band')).toBe('light band')
  expect(label({ kit: 'pull-up bar', note: '' }, 'pull-up bar')).toBe('pull-up bar')
})
