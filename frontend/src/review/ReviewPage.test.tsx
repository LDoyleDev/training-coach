import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { WeekReview } from '../api'
import ReviewPage from './ReviewPage'

const WEEK: WeekReview = {
  start: '2026-10-05',
  current: true,
  previous: '2026-09-28',
  next: null,
  planned: 7,
  done: 3,
  rested: 1,
  extras: 1,
  sets: [
    { group: 'back', sets: 22 },
    { group: 'chest', sets: 12 },
    { group: 'legs', sets: 6 },
  ],
  sets_target: [10, 20],
  zone2_minutes: 95,
  zone2_target: [180, 200],
  moderate_minutes: 20,
  bests: [
    {
      exercise: 'Pull-up',
      step: 'Full',
      kind: 'reps',
      best_set: 8,
      total: 30,
      strength: false,
      load_kg: null,
    },
    {
      exercise: 'Plank',
      step: 'Long',
      kind: 'seconds',
      best_set: 90,
      total: null,
      strength: true,
      load_kg: null,
    },
    {
      exercise: 'Hammer curl',
      step: 'Dumbbells',
      kind: 'reps',
      best_set: 12,
      total: null,
      strength: false,
      load_kg: 12.5,
    },
  ],
  ready: [{ exercise: 'Push-up', slug: 'push-up' }],
  top: [
    {
      exercise: 'Kettlebell swing',
      slug: 'kb-swing',
      unlock: 'a 16 kg kettlebell unlocks Two-hand, 16 kg',
      capped: true,
    },
  ],
  strength_block: false,
  habits: [{ label: 'Wind-down', done: 2, days: 3 }],
  ai_comments: true,
  ai_comment: null,
}

function serve(answer: WeekReview | 'signed-out' | 'error' = WEEK, search = '') {
  window.history.pushState({}, '', `/review${search}`)
  const fetchMock = vi.fn(async () => {
    if (answer === 'signed-out') return new Response(null, { status: 401 })
    if (answer === 'error') return new Response(null, { status: 500 })
    return Response.json(answer)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

test('this week so far, as the bot sends it', async () => {
  const fetchMock = serve()
  render(<ReviewPage />)
  expect(await screen.findByRole('heading', { name: 'This week' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/review', expect.anything())
  expect(screen.getByText('3 of 7 done (1 rest day, 1 extra).')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Hard sets per muscle (aim 10-20)' })).toBeVisible()
  expect(screen.getByText('22 (high)')).toBeInTheDocument()
  expect(screen.getByText('6 (low)')).toBeInTheDocument()
  expect(screen.getByText('Zone 2: 95 of 180-200 min (85 short)')).toBeInTheDocument()
  expect(screen.getByText('Pull-up (Full): 8 reps in one set and 30 reps in total')).toBeVisible()
  expect(screen.getByText('Plank (Long, strength block): 90 s in one set')).toBeVisible()
  // Bests count every weight here, so a loaded step's names its session's (ADR-0072).
  expect(
    screen.getByText(/^Hammer curl \(Dumbbells, at 12\.5 kg\): 12 reps in one set$/),
  ).toBeVisible()
  expect(screen.getByRole('link', { name: 'Push-up' })).toHaveAttribute(
    'href',
    '/plan?move=push-up',
  )
  expect(
    screen.getByText(/Choose on the Plan page, or when asked after your next session/),
  ).toBeVisible()
  // Reached the top this week with the next level locked by kit (ADR-0078)
  const top = screen.getByRole('heading', { name: 'At the top' }).closest('section')
  expect(top).toHaveTextContent(
    'Kettlebell swing: top of the range on the last level your kit allows. ' +
      'A 16 kg kettlebell unlocks Two-hand, 16 kg. My equipment',
  )
  expect(screen.getByRole('link', { name: 'My equipment' })).toHaveAttribute(
    'href',
    '/account#my-equipment',
  )
  expect(screen.getByText('2 of 3 so far')).toBeInTheDocument()
  expect(screen.getByText(/AI comment from your Groq key comes on Telegram/)).toBeVisible()
  expect(screen.queryByRole('region', { name: 'AI comment' })).toBeNull()
  expect(screen.getByRole('link', { name: 'Week before' })).toHaveAttribute(
    'href',
    '/review?week=2026-09-28',
  )
  expect(screen.queryByRole('link', { name: 'Week after' })).toBeNull()
})

test('an earlier week, a quiet one', async () => {
  const fetchMock = serve(
    {
      ...WEEK,
      start: '2026-09-28',
      current: false,
      previous: '2026-09-21',
      next: '2026-10-05',
      done: 0,
      rested: 0,
      extras: 0,
      sets: [],
      zone2_target: null,
      zone2_minutes: 0,
      bests: [],
      ready: [],
      top: [],
      habits: [],
      ai_comments: false,
    },
    '?week=2026-09-28',
  )
  render(<ReviewPage />)
  expect(await screen.findByRole('heading', { name: 'Week of Mon 28 Sept' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'At the top' })).toBeNull()
  expect(fetchMock).toHaveBeenCalledWith('/api/review?week=2026-09-28', expect.anything())
  expect(screen.getByText('0 of 7 done.')).toBeInTheDocument()
  expect(screen.getByText('No sets logged this week.')).toBeInTheDocument()
  expect(screen.getByText('Zone 2: 0 min')).toBeInTheDocument()
  expect(screen.queryByText(/AI comment/)).toBeNull()
  expect(screen.getByRole('link', { name: 'Week after' })).toHaveAttribute(
    'href',
    '/review?week=2026-10-05',
  )
  expect(screen.getByRole('link', { name: 'This week' })).toHaveAttribute('href', '/review')
})

test("the week's AI comment shows as plain text under the review", async () => {
  serve({
    ...WEEK,
    ai_comment: 'Good week.\n- Sleep more.\n<b>not bold</b> **not strong** <img src=x>',
  })
  render(<ReviewPage />)
  const comment = await screen.findByRole('region', { name: 'AI comment' })
  expect(comment).toHaveTextContent('AI comment (from your Groq key, a suggestion only)')
  expect(comment).toHaveTextContent(
    'Good week. - Sleep more. <b>not bold</b> **not strong** <img src=x>',
  )
  expect(comment.querySelector('b, strong, img')).toBeNull()
  expect(screen.queryByText(/comes on Telegram/)).toBeNull()
})

test('ready to move up waits for the hypertrophy block', async () => {
  serve({ ...WEEK, strength_block: true })
  render(<ReviewPage />)
  expect(await screen.findByText('When the hypertrophy block starts.')).toBeVisible()
  expect(screen.getByRole('link', { name: 'Push-up' })).toHaveAttribute(
    'href',
    '/plan?move=push-up',
  )
})

test('signed out points to sign in', async () => {
  serve('signed-out')
  render(<ReviewPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
})

test('an error offers to try again', async () => {
  serve('error')
  render(<ReviewPage />)
  expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
})
