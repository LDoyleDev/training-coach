import { expect, test } from 'vitest'
import {
  BODY_KNOWS,
  INTENDED_PURPOSE,
  LAST_SET_LINE,
  NORMAL,
  STOP_LINE,
  STOP_SIGNS,
  TALK_TEST,
} from './safety'

const ALL = [
  INTENDED_PURPOSE,
  NORMAL,
  BODY_KNOWS,
  STOP_LINE,
  LAST_SET_LINE,
  ...TALK_TEST,
  ...STOP_SIGNS.flatMap(({ signs, then }) => [signs, then]),
]

test('chest pain names 112, a time limit, and not driving yourself (Part 5)', () => {
  const chest = STOP_SIGNS.find(({ signs }) => signs.includes('chest'))
  expect(chest?.then).toMatch(/Call 112 straight away/)
  expect(chest?.then).toMatch(/after 5 minutes of rest/)
  expect(chest?.then).toMatch(/Don't drive yourself/)
})

test('the one-line reminder names 112 too', () => {
  expect(STOP_LINE).toMatch(/Call 112 if it's severe or doesn't ease with rest/)
})

test('illness and pregnancy have their own stop signs, shown to everyone', () => {
  expect(STOP_SIGNS.map(({ signs }) => signs)).toEqual(
    expect.arrayContaining(['A fever, or feeling ill', expect.stringMatching(/pregnant/)]),
  )
})

test('the wording never promises safety, clears anyone or diagnoses (ADR-0085)', () => {
  for (const text of ALL) expect(text).not.toMatch(/\bsafe|\bclear(ed)?\b|diagnos(is|ed)\b/i)
})

test('the intended purpose says it is a fitness app that assesses no one', () => {
  expect(INTENDED_PURPOSE).toMatch(/general fitness app for adults living in the EU or EEA/)
  expect(INTENDED_PURPOSE).toMatch(/doesn't assess your health/)
  expect(INTENDED_PURPOSE).toMatch(/You decide what you do\.$/)
})
