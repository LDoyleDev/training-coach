import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Equipment, MessageSettings } from '../api'
import { QUESTIONS, VERSION } from '../readiness/questions'
import type { WalkLadder } from './api'
import StartPage from './StartPage'

const SETTINGS = {
  places: 'home',
  avoid_floor: false,
  avoid_kneeling: false,
  avoid_impact: false,
  avoid_hanging: false,
  avoid_knees: false,
} as MessageSettings
const KIT: Equipment = {
  items: [],
  kinds: [
    { kit: 'kettlebell', name: 'kettlebell' },
    { kit: 'mat', name: 'mat' },
  ],
  listed: false,
  saved_at: null,
}
const ANSWERED = '2026-11-03T09:00:00Z'
const step = (id: number, name: string, level: number, question: string | null, marks = []) => ({
  id,
  position: id - 1,
  name,
  level,
  question,
  cue: `The cue for ${name}.`,
  needs: [],
  marks,
})
const PUSH_UP: WalkLadder = {
  slug: 'push-up',
  name: 'Push-up',
  on: null,
  steps: [
    step(1, 'Hands on a wall', 1, null),
    step(
      2,
      'Hands on a counter',
      2,
      'Can you do 10 push-ups with your hands on a kitchen counter?',
    ),
    step(3, 'Hands on a table', 3, 'Can you do 10 push-ups with your hands on a table?'),
    {
      ...step(4, 'Standard', 4, 'Can you do 10 push-ups from the floor, body straight?'),
      marks: ['floor'],
    },
  ],
}

interface Server {
  role?: 'admin' | 'member'
  consent?: boolean // the walkthrough category is open
  country?: string | null
  due?: boolean
  status?: number // every GET answers this instead
  told?: number // what telling the server the health questions were answered answers
}

/** A fake API by path; every request with a method is kept, to show what was written. */
function serve({
  role = 'member',
  consent = false,
  country = null,
  due = true,
  status,
  told = 200,
}: Server) {
  const writes: [string, string, unknown][] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method) {
        writes.push([init.method, path, init.body ? JSON.parse(String(init.body)) : null])
        if (path === '/api/readiness' && told !== 200) return new Response(null, { status: told })
        if (path === '/api/readiness')
          return Response.json({ version: VERSION, due: false, answered_at: ANSWERED })
        return Response.json({ asked: true, categories: [] })
      }
      if (status) return new Response(null, { status })
      const body: Record<string, unknown> = {
        '/api/auth/me': { role, user_id: 2, closed: false },
        '/api/consents': {
          asked: true,
          categories: [{ category: 'walkthrough', open: consent, version: 2 }],
        },
        '/api/account/residence': { choices: ['DE', 'IE'], country },
        '/api/settings': SETTINGS,
        '/api/equipment': KIT,
        '/api/walkthrough': { ladders: [PUSH_UP] },
        '/api/readiness': {
          version: VERSION,
          due,
          answered_at: due ? null : ANSWERED,
          ask_again_after: null,
        },
      }
      return Response.json(body[path])
    }),
  )
  return writes
}

afterEach(() => vi.unstubAllGlobals())

const tap = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('a new member: every screen in order, with Back, and only the health version told', async () => {
  const writes = serve({})
  render(<StartPage />)
  expect(await screen.findByRole('heading', { name: 'Set up your plan' })).toBeInTheDocument()
  expect(screen.queryByText(/try-out/)).not.toBeInTheDocument()
  tap('Start')

  expect(screen.getByText('1 of 12')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Keep your walk-through answers?' })).toHaveFocus()
  tap('Not now')

  expect(screen.getByText('2 of 12')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Where you live' })).toBeInTheDocument()
  tap('Next')

  expect(screen.getByText('3 of 12')).toBeInTheDocument()
  expect(screen.getByText(/Your answers stay on this device/)).toBeInTheDocument()
  QUESTIONS.forEach((q, i) => {
    expect(screen.getByRole('heading', { name: q.text })).toBeInTheDocument()
    tap(i === 0 ? 'Yes' : 'No')
  })
  expect(await screen.findByText('Start easy and build up')).toBeInTheDocument()
  tap('Next')

  expect(screen.getByText('4 of 12')).toBeInTheDocument()
  tap('50 to 64')
  tap('Back')
  expect(screen.getByRole('button', { name: '50 to 64' })).toHaveAttribute('aria-pressed', 'true')
  tap('50 to 64')
  tap('Not at the moment') // how hard and how long are then not asked
  expect(screen.getByText('6 of 12')).toBeInTheDocument()
  tap('Yes') // chair
  tap('Skip') // stairs
  tap('Yes') // walk
  tap('No') // floor

  expect(screen.getByText('7 of 12')).toBeInTheDocument()
  const floor = screen.getByRole('button', { name: /Keep me off the floor/ })
  expect(floor).toHaveTextContent('Off · Suggested')
  expect(floor).toHaveAttribute('aria-pressed', 'false') // a suggestion, off until tapped
  fireEvent.click(floor)
  expect(floor).toHaveAttribute('aria-pressed', 'true')
  tap('Next')

  expect(screen.getByText('8 of 12')).toBeInTheDocument()
  tap(/Gym/) // the home kit isn't asked

  // Level 2 (not exercising now): the counter first. Off the floor: Standard is never asked.
  expect(screen.getByText('9 of 12')).toBeInTheDocument()
  expect(screen.getByText('Push-up, exercise 1 of 1')).toBeInTheDocument()
  expect(screen.getByText('The cue for Hands on a counter.')).toBeInTheDocument()
  expect(screen.getByText('Not sure? Try one now, holding a counter.')).toBeInTheDocument()
  tap('Yes')
  expect(screen.getByRole('heading', { name: /hands on a table/ })).toHaveFocus()
  tap('Back')
  expect(screen.getByRole('heading', { name: /kitchen counter/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'true')
  tap('Yes')
  tap('Not sure') // the table: counted as No, so the counter it is

  expect(screen.getByText('10 of 12')).toBeInTheDocument()
  tap('Monday')
  tap('Thursday')
  tap('Monday')
  tap('Wednesday')
  expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'false')
  expect(screen.getByRole('button', { name: 'Wednesday' })).toHaveAttribute('aria-pressed', 'true')
  tap('Next')
  expect(screen.getByText('11 of 12')).toBeInTheDocument()
  tap('30 minutes')
  expect(screen.getByText('12 of 12')).toBeInTheDocument()
  tap('6')
  expect(screen.getByRole('heading', { name: 'Next: your plan' })).toBeInTheDocument()
  tap('Back')
  expect(screen.getByRole('button', { name: '6' })).toHaveAttribute('aria-pressed', 'true')

  // Only that the health questions were answered (the version) and nothing else.
  expect(writes).toEqual([['PUT', '/api/readiness', { version: VERSION }]])
})

test('the home kit is held in memory until Save', async () => {
  const writes = serve({ consent: true, country: 'IE', due: false })
  render(<StartPage />)
  await screen.findByRole('button', { name: 'Start' })
  tap('Start')
  for (const answer of ['Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip']) tap(answer)
  tap('Next') // avoid
  tap(/Home/)
  expect(screen.getByText(/No kit listed: nothing is locked/)).toBeInTheDocument()
  tap('+ mat')
  tap('Add to my kit')
  expect(screen.getByText('mat')).toBeInTheDocument()
  expect(screen.queryByText(/Checking what it unlocks/)).not.toBeInTheDocument()
  tap('Next')
  // Nothing answered: level 4, and the floor is open.
  expect(screen.getByRole('heading', { name: /from the floor/ })).toBeInTheDocument()
  tap('Back')
  expect(screen.getByText('mat')).toBeInTheDocument() // kept while going back and forth
  expect(writes).toEqual([])
})

test('a change to what the walk depends on starts its answers again', async () => {
  serve({ consent: true, country: 'IE', due: false })
  render(<StartPage />)
  await screen.findByRole('button', { name: 'Start' })
  tap('Start')
  for (const answer of ['Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip', 'Skip']) tap(answer)
  tap('Next') // avoid
  tap(/Gym/)
  tap('Yes') // Standard, the top: done
  expect(screen.getByText('10 of 12')).toBeInTheDocument()
  tap('Back')
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'true')
  tap('Back')
  tap(/Gym/) // the same answer keeps them
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'true')
  tap('Back')
  tap('Back')
  tap('Next') // the switches as they were
  tap(/Gym/)
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'true')
  for (let i = 0; i < 3; i++) tap('Back') // to the floor question, skipped before
  tap('Skip') // skipped again: the same answers
  tap('Next')
  tap(/Gym/)
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'true')
  tap('Back')
  tap(/Both/)
  tap('Next') // the kit
  expect(screen.getByRole('button', { name: 'Yes' })).toHaveAttribute('aria-pressed', 'false')
  tap('Skip this one')
  expect(screen.getByText('10 of 12')).toBeInTheDocument()
  tap('Next')
  tap('Skip') // minutes: as Account has them
  tap('Skip') // count
  expect(screen.getByRole('heading', { name: 'Next: your plan' })).toBeInTheDocument()
})

test('the owner gets a try-out, and screens the server already has are skipped', async () => {
  serve({ role: 'admin', consent: true, country: 'DE', due: false })
  render(<StartPage />)
  expect(await screen.findByText("This is a try-out: your plan won't change.")).toBeInTheDocument()
  tap('Start')
  expect(screen.getByText('You answered the health questions on 3 Nov 2026.')).toBeInTheDocument()
  expect(screen.getByText('4 of 12')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'How old are you?' })).toHaveFocus()
})

test('the health questions can be put off: nothing is told, and they come back next time', async () => {
  const writes = serve({ consent: true, country: 'IE' })
  render(<StartPage />)
  await screen.findByRole('button', { name: 'Start' })
  tap('Start')
  tap('Not now')
  expect(screen.getByRole('heading', { name: 'How old are you?' })).toBeInTheDocument()
  expect(screen.queryByText(/You answered the health questions/)).not.toBeInTheDocument()
  tap('Back')
  expect(screen.getByRole('heading', { name: QUESTIONS[0].text })).toBeInTheDocument()
  expect(writes).toEqual([])
})

test('a yes to keeping the answers gives the walkthrough consent at its wording version', async () => {
  const writes = serve({ country: 'IE', due: false })
  render(<StartPage />)
  await screen.findByRole('button', { name: 'Start' })
  tap('Start')
  tap('Yes, keep it')
  expect(await screen.findByRole('heading', { name: 'How old are you?' })).toBeInTheDocument()
  expect(writes).toEqual([['PUT', '/api/consents/walkthrough', { version: 2 }]])
})

test.each([
  [409, 'The questions have changed since this page loaded.'],
  [500, "Couldn't save that you answered, so we'll ask again next time."],
])('the note still shows when telling the server fails (%i)', async (told, said) => {
  serve({ consent: true, country: 'IE', told })
  render(<StartPage />)
  await screen.findByRole('button', { name: 'Start' })
  tap('Start')
  QUESTIONS.forEach(() => tap('Not sure'))
  expect(await screen.findByRole('alert')).toHaveTextContent(said)
  expect(screen.getByText('Talk to a doctor before you start')).toBeInTheDocument()
})

test('signed out, it asks to sign in; an error offers to try again', async () => {
  serve({ status: 401 })
  const { unmount } = render(<StartPage />)
  expect(await screen.findByText('Sign in to set up your plan.')).toBeInTheDocument()
  unmount()
  serve({ status: 500 })
  render(<StartPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load the walk-through.")
})
