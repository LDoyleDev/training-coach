import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { Clash } from '../api'
import ClashQuestion from './ClashQuestion'
import { dayText, recentDays } from './logic'

const LEGS: Clash = {
  day: '2026-10-08',
  moving: false,
  recorded: [{ workout_id: 7, name: 'Legs', summary: '25 sets: Jump squat, Kettlebell swing' }],
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('it shows what is there and sends each answer with what was seen', () => {
  const onAnswer = vi.fn()
  render(<ClashQuestion clash={LEGS} onAnswer={onAnswer} onCancel={() => {}} />)
  expect(screen.getByRole('alertdialog')).toHaveTextContent(
    'Thu 08 Oct already has a session' + 'Legs: 25 sets: Jump squat, Kettlebell swing',
  )
  click('Replace it')
  click('Add to that day')
  expect(onAnswer.mock.calls).toEqual([
    [{ resolution: 'replace', seen: [7] }],
    [{ resolution: 'add', seen: [7] }],
  ])
})

test('moving picks another day in the last two weeks', () => {
  const onAnswer = vi.fn()
  render(<ClashQuestion clash={LEGS} onAnswer={onAnswer} onCancel={() => {}} />)
  click('Move it to another day')
  const days = screen.getAllByRole('button').map((b) => b.textContent)
  expect(days).not.toContain('Thu 08 Oct') // not the day it's on
  click('Back')
  click('Move it to another day')
  fireEvent.click(screen.getAllByRole('button')[0])
  expect(onAnswer).toHaveBeenCalledWith({ resolution: `move:${recentDays()[0]}`, seen: [7] })
})

test('a day that holds a session too asks for another one', () => {
  const taken: Clash = {
    day: recentDays()[1],
    moving: true,
    recorded: [{ workout_id: 9, name: 'Long zone 2', summary: '45 min' }],
  }
  render(<ClashQuestion clash={LEGS} taken={taken} onAnswer={() => {}} onCancel={() => {}} />)
  expect(screen.getByRole('status')).toHaveTextContent(
    `${dayText(taken.day)} has Long zone 2 (45 min) too. Pick another day.`,
  )
  const days = screen.getAllByRole('button').map((b) => b.textContent)
  expect(days).not.toContain(dayText(taken.day))
})

test('two sessions on the day are named together, and Cancel cancels', () => {
  const onCancel = vi.fn()
  const both: Clash = {
    ...LEGS,
    recorded: [...LEGS.recorded, { workout_id: 8, name: 'Rest day', summary: 'rested' }],
  }
  render(<ClashQuestion clash={both} onAnswer={() => {}} onCancel={onCancel} />)
  expect(screen.getByText('What should happen to them?')).toBeInTheDocument()
  click('Cancel')
  expect(onCancel).toHaveBeenCalled()
})

test('recent days run from today back two weeks', () => {
  const days = recentDays(new Date(2026, 9, 12))
  expect(days).toHaveLength(15)
  expect([days[0], days[14]]).toEqual(['2026-10-12', '2026-09-28'])
})
