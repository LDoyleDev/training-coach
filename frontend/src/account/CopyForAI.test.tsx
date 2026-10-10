import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import CopyForAI, { QUESTION } from './CopyForAI'

const SUMMARY = '# My training (Training Coach)\nRead the guide first: https://example/guide\n'

function serve(status = 200) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      asked.push(path)
      return status === 200 ? new Response(SUMMARY, { status }) : new Response(null, { status })
    }),
  )
  return asked
}

function clipboard(works: boolean) {
  const writeText = vi.fn(async () => {
    if (!works) throw new Error('not allowed')
  })
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
  return writeText
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('copies the question and the summary, without health data by default', async () => {
  const asked = serve()
  const writeText = clipboard(true)
  render(<CopyForAI />)
  fireEvent.click(screen.getByRole('button', { name: 'Copy for my AI' }))
  expect(await screen.findByText('Copied. Paste it into your AI.')).toBeInTheDocument()
  expect(asked).toEqual(['/api/account/ai-summary?period=4w&body=false&readiness=false'])
  expect(writeText).toHaveBeenCalledWith(`${QUESTION}\n\n${SUMMARY}`)
})

test('the question, period and health data are the person’s choice', async () => {
  const asked = serve()
  const writeText = clipboard(true)
  render(<CopyForAI />)
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Am I improving?' } })
  fireEvent.change(screen.getByLabelText('Period'), { target: { value: 'all' } })
  fireEvent.click(screen.getByLabelText('Include body measurements (health data)'))
  fireEvent.click(screen.getByLabelText('Include readiness answers (health data)'))
  fireEvent.click(screen.getByRole('button', { name: 'Copy for my AI' }))
  await screen.findByText('Copied. Paste it into your AI.')
  expect(asked).toEqual(['/api/account/ai-summary?period=all&body=true&readiness=true'])
  expect(writeText).toHaveBeenCalledWith(`Am I improving?\n\n${SUMMARY}`)
})

test('without a clipboard the text is shown to copy by hand', async () => {
  serve()
  clipboard(false)
  render(<CopyForAI />)
  fireEvent.click(screen.getByRole('button', { name: 'Copy for my AI' }))
  const manual = await screen.findByLabelText(/select all of this and copy it/)
  expect((manual as HTMLTextAreaElement).value).toBe(`${QUESTION}\n\n${SUMMARY}`)
})

test('an ended sign-in and a failed request say so', async () => {
  serve(401)
  clipboard(true)
  const { unmount } = render(<CopyForAI />)
  fireEvent.click(screen.getByRole('button', { name: 'Copy for my AI' }))
  expect(await screen.findByText(/Your sign-in ended/)).toBeInTheDocument()
  unmount()
  serve(500)
  render(<CopyForAI />)
  fireEvent.click(screen.getByRole('button', { name: 'Copy for my AI' }))
  expect(await screen.findByText(/Couldn't get your training/)).toBeInTheDocument()
})
