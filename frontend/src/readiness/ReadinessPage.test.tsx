import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Readiness } from '../api'
import ReadinessPage from './ReadinessPage'
import { NOTES, QUESTIONS, VERSION } from './questions'

const DUE: Readiness = { version: VERSION, due: true, answered_at: null, ask_again_after: null }

function serve(readiness: Readiness | null | 'error', saved = 200) {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        sent.push(JSON.parse(String(init.body)))
        if (saved !== 200) return new Response(null, { status: saved })
        return Response.json({
          ...DUE,
          due: false,
          answered_at: '2026-11-08T12:00:00Z',
          ask_again_after: '2027-11-08T12:00:00Z',
        })
      }
      if (readiness === 'error') return new Response(null, { status: 500 })
      if (readiness === null) return new Response(null, { status: 401 })
      return Response.json(readiness)
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
})

/** One answer's radio in a question's fieldset. */
function within(question: string, value: 'Yes' | 'No' | 'Not sure'): HTMLElement {
  const group = screen.getByRole('group', { name: question })
  const radio = Array.from(group.querySelectorAll('label')).find((l) => l.textContent === value)
  if (!radio) throw new Error(`no ${value} for ${question}`)
  return radio.querySelector('input') as HTMLElement
}

async function answerAll(except: Record<number, 'Yes' | 'No' | 'Not sure'> = {}) {
  await screen.findByRole('group', { name: QUESTIONS[0].text })
  QUESTIONS.forEach((q, i) =>
    fireEvent.click(within(q.text, except[i] ?? (i === 0 ? 'Yes' : 'No'))),
  )
}

test('the intro suggests a doctor, leaves the choice to you and says the answers stay here', async () => {
  serve(DUE)
  render(<ReadinessPage />)
  const intro = await screen.findByText(/A "yes" never stops you/)
  expect(intro).toHaveTextContent('we suggest talking to a doctor first. You decide.')
  expect(intro).toHaveTextContent('Your answers stay on this device.')
  expect(screen.queryByText(/cleared|safe for you|risk score/i)).not.toBeInTheDocument()
})

test('every question needs an answer; the note is worked out here and only the version sent', async () => {
  const sent = serve(DUE)
  render(<ReadinessPage />)
  const save = await screen.findByRole('button', { name: 'See what we suggest' })
  expect(save).toBeDisabled()
  await answerAll({ 2: 'Yes' }) // a heart condition
  fireEvent.click(save)
  expect(
    await screen.findByRole('heading', { name: NOTES.easy_ask_before_hard.title }),
  ).toBeInTheDocument()
  expect(await screen.findByText(/asked again after 8 Nov 2027/)).toBeInTheDocument()
  expect(sent).toEqual([{ version: VERSION }])
})

test('inactive and 35 or over: start easy and ask before hard sessions', async () => {
  serve(DUE)
  render(<ReadinessPage />)
  await answerAll({ 0: 'No', 1: 'Yes' })
  fireEvent.click(screen.getByRole('button', { name: 'See what we suggest' }))
  expect(
    await screen.findByRole('heading', { name: NOTES.easy_ask_before_hard.title }),
  ).toBeInTheDocument()
})

test('pregnancy suggests a midwife or doctor before starting', async () => {
  serve(DUE)
  render(<ReadinessPage />)
  await answerAll({ 9: 'Yes' })
  fireEvent.click(screen.getByRole('button', { name: 'See what we suggest' }))
  expect(await screen.findByRole('heading', { name: NOTES.doctor_first.title })).toBeInTheDocument()
  expect(screen.getByText(NOTES.doctor_first.text)).toBeInTheDocument() // names a midwife too
})

test('no answers are filled in from before, only when they were given', async () => {
  serve({
    ...DUE,
    due: false,
    answered_at: '2026-10-10T12:00:00Z',
    ask_again_after: '2027-10-10T12:00:00Z',
  })
  render(<ReadinessPage />)
  expect(
    await screen.findByText(/Answered 10 Oct 2026; asked again after 10 Oct 2027/),
  ).toBeInTheDocument()
  expect(within(QUESTIONS[0].text, 'Yes')).not.toBeChecked()
  expect(screen.getByRole('button', { name: 'See what we suggest' })).toBeDisabled()
})

test('signed out, it points to sign in', async () => {
  serve(null)
  render(<ReadinessPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute(
    'href',
    expect.stringMatching(/^\/signin\?next=/),
  )
})

test('a failed load says so', async () => {
  serve('error')
  render(<ReadinessPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load the questions")
})

test('a sign-in that ended while saving points to sign in again, with the note shown', async () => {
  serve(DUE, 401)
  render(<ReadinessPage />)
  await answerAll()
  fireEvent.click(screen.getByRole('button', { name: 'See what we suggest' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: NOTES.easy.title })).toBeInTheDocument()
})

test.each([
  [500, "Couldn't save that you answered"],
  [409, 'Reload to answer the new ones'],
])('a failed save (%s) says so and still shows the note', async (status, text) => {
  serve(DUE, status)
  render(<ReadinessPage />)
  await answerAll()
  fireEvent.click(screen.getByRole('button', { name: 'See what we suggest' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
  expect(screen.getByRole('heading', { name: NOTES.easy.title })).toBeInTheDocument()
})
