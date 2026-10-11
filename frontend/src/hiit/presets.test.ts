import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { DEFAULTS } from './logic'
import { DEFAULT_PRESETS, loadPresets, loadVoice, newId, savePresets, saveVoice } from './presets'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('a new browser has the Tabata workout', () => {
  expect(loadPresets()).toEqual([{ id: 'tabata', name: 'Tabata', settings: DEFAULTS }])
})

test('saved workouts come back, cleaned up', () => {
  savePresets([{ id: 'a', name: 'Bike', settings: { ...DEFAULTS, work: 30 } }])
  expect(loadPresets()).toEqual([{ id: 'a', name: 'Bike', settings: { ...DEFAULTS, work: 30 } }])
  localStorage.setItem(
    'training-coach:hiit-workouts',
    JSON.stringify([
      { id: 'b', name: '  Rower  ', settings: { work: 9999 } },
      { id: 'c', name: '' },
      null,
      { name: 'no id' },
    ]),
  )
  expect(loadPresets()).toEqual([{ id: 'b', name: 'Rower', settings: { ...DEFAULTS, work: 900 } }])
})

test('an empty saved list stays empty; unreadable data falls back to the defaults', () => {
  savePresets([])
  expect(loadPresets()).toEqual([])
  localStorage.setItem('training-coach:hiit-workouts', '{not json')
  expect(loadPresets()).toBe(DEFAULT_PRESETS)
  localStorage.setItem('training-coach:hiit-workouts', '{"a":1}')
  expect(loadPresets()).toBe(DEFAULT_PRESETS)
})

test('blocked storage: the defaults, and saving quietly does nothing', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(loadPresets()).toBe(DEFAULT_PRESETS)
  expect(loadVoice()).toBe(false)
  expect(() => savePresets([])).not.toThrow()
  expect(() => saveVoice(true)).not.toThrow()
})

test('the voice setting is remembered, off by default', () => {
  expect(loadVoice()).toBe(false)
  saveVoice(true)
  expect(loadVoice()).toBe(true)
  saveVoice(false)
  expect(loadVoice()).toBe(false)
})

test('ids are unique enough for a short list', () => {
  expect(newId()).not.toBe(newId())
})
