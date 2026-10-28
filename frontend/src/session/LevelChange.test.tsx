import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { ItemLevel } from '../api'
import LevelChange from './LevelChange'

const LEVEL: ItemLevel = {
  step_id: 11,
  for_today: false,
  ladder: [
    { id: 10, name: 'Two-hand, 8 kg', cue: null, missing: [] },
    { id: 11, name: 'One-arm, 8 kg', cue: 'Square shoulders.', missing: [] },
    { id: 12, name: 'Two-hand, 16 kg', cue: null, missing: ['a 16 kg kettlebell'] },
    { id: 13, name: 'One-arm, 16 kg', cue: null, missing: ['a 16 kg kettlebell'] },
  ],
}

function shown(level: ItemLevel = LEVEL, done = 0, answer = true) {
  const onPick = vi.fn(async () => answer)
  render(
    <LevelChange
      name="Kettlebell swing"
      step="One-arm, 8 kg"
      level={level}
      done={done}
      busy={false}
      onPick={onPick}
    />,
  )
  return onPick
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('the ladder opens one level down and up first, every level on request', () => {
  shown()
  expect(screen.getByText('One-arm, 8 kg')).toBeInTheDocument()
  click('Change level')
  const group = screen.getByRole('group', { name: 'Level for Kettlebell swing' })
  expect(group).toBeInTheDocument()
  expect(screen.getAllByRole('radio')).toHaveLength(3)
  expect(screen.getByRole('radio', { name: /One-arm, 8 kg \(today\)/ })).toBeChecked()
  expect(screen.getByText('Square shoulders.')).toBeInTheDocument() // the step's cue
  expect(
    screen.getByRole('radio', { name: /Two-hand, 16 kg · Locked: needs a 16 kg kettlebell/ }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'For today' })).not.toBeInTheDocument()
  click('All levels (4)')
  expect(screen.getAllByRole('radio')).toHaveLength(4)
  click('Fewer levels')
  expect(screen.getAllByRole('radio')).toHaveLength(3)
  click('Cancel')
  expect(screen.queryByRole('group')).not.toBeInTheDocument()
})

test('a level asks for today or from now on, with the kit warning and the sets done', async () => {
  const onPick = shown(LEVEL, 2)
  click('Change level')
  fireEvent.click(screen.getByRole('radio', { name: /Two-hand, 16 kg/ }))
  expect(
    screen.getByText('Targets for Two-hand, 16 kg start fresh from its own history.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText(
      'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit. You can still choose it.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByText('The 2 sets you’ve done stay at One-arm, 8 kg.')).toBeInTheDocument()
  expect(screen.getByText('For today, or from now on?')).toBeInTheDocument()
  click('For today')
  expect(onPick).toHaveBeenCalledWith(12, 'Two-hand, 16 kg', 'today')
  expect(await screen.findByRole('button', { name: 'Change level' })).toBeInTheDocument()
})

test('from now on is the other answer; a refused change keeps the picker open', async () => {
  const onPick = shown(LEVEL, 1, false)
  click('Change level')
  fireEvent.click(screen.getByRole('radio', { name: /Two-hand, 8 kg/ }))
  expect(screen.getByText('The set you’ve done stays at One-arm, 8 kg.')).toBeInTheDocument()
  click('From now on')
  expect(onPick).toHaveBeenCalledWith(10, 'Two-hand, 8 kg', 'from_now_on')
  await Promise.resolve()
  expect(screen.getByRole('group', { name: 'Level for Kettlebell swing' })).toBeInTheDocument()
})

test('a level chosen for today only says so; a short ladder has no "all levels"', () => {
  shown({ ...LEVEL, for_today: true, ladder: LEVEL.ladder.slice(0, 3) })
  expect(screen.getByText('· for today only', { exact: false })).toBeInTheDocument()
  click('Change level')
  expect(screen.queryByRole('button', { name: /All levels/ })).not.toBeInTheDocument()
})
