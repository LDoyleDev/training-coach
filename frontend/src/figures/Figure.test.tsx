import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Figure, { FigureAt } from './Figure'

afterEach(() => vi.unstubAllGlobals())

function motion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: reduce && query.includes('reduce') }))
}

test('the figure moves from start to end, and can show both positions instead', async () => {
  motion(false)
  const frames: FrameRequestCallback[] = []
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {})
  render(<Figure slug="cat-cow" name="Cat–cow" />)
  const moving = screen.getByRole('img', { name: /^Cat–cow, moving from: Cat: round the back/ })
  const before = moving.innerHTML
  act(() => frames.shift()!(performance.now() + 1300)) // half way to the end
  expect(moving.innerHTML).not.toBe(before)

  fireEvent.click(screen.getByRole('button', { name: 'Start and end' }))
  expect(screen.getByRole('button', { name: 'Start and end' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(
    screen.getByRole('img', { name: 'Cat–cow, start: Cat: round the back, chin to chest' }),
  ).toBeVisible()
  expect(screen.getByRole('img', { name: /^Cat–cow, end: Cow/ })).toBeVisible()
  expect(screen.getByText('Start.')).toBeInTheDocument()
  expect(screen.getByText('End.')).toBeInTheDocument()
})

test('people who ask for less motion see the two positions', () => {
  motion(true)
  render(<Figure slug="glute-bridge" name="Glute bridge" />)
  expect(screen.getAllByRole('img')).toHaveLength(2)
  expect(screen.getByRole('button', { name: 'Start and end' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('off screen it stops redrawing', () => {
  motion(false)
  const frames: FrameRequestCallback[] = []
  let report: (entries: { isIntersecting: boolean }[]) => void = () => {}
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {})
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(cb: typeof report) {
        report = cb
      }
      observe() {}
      disconnect() {}
    },
  )
  render(<Figure slug="y-reach" name="Standing Y-reach" />)
  const drawing = screen.getByRole('img')
  const before = drawing.innerHTML
  report([{ isIntersecting: false }])
  act(() => frames.shift()!(performance.now() + 1000))
  expect(drawing.innerHTML).toBe(before)
})

test('a slug without a figure shows nothing', () => {
  motion(false)
  const { container } = render(
    <>
      <Figure slug="no-such-move" name="Mystery" />
      <FigureAt slug="no-such-move" t={0} label="Mystery" />
    </>,
  )
  expect(container).toBeEmptyDOMElement()
})

test('a still drawing at any point of the movement', () => {
  render(<FigureAt slug="push-up" t={1} label="Push-up, bottom" />)
  const drawing = screen.getByRole('img', { name: 'Push-up, bottom' })
  expect(drawing.querySelectorAll('path').length).toBeGreaterThan(10)
  expect(drawing).toHaveAttribute('viewBox', '-14 -86 188 89')
})

test("a drawing doesn't take the page's section style (no top rule, no padding)", () => {
  render(<FigureAt slug="push-up" t={0} label="Push-up, top" />)
  const drawing = screen.getByRole('img', { name: 'Push-up, top' })
  expect(drawing).not.toHaveClass('block') // index.css styles `.block` as a page section
  expect(drawing).toHaveStyle({ display: 'block' })
})

test('a figure drawn from the front as well starts there and switches to the side', () => {
  motion(true)
  render(<Figure slug="copenhagen-plank" name="Copenhagen plank" />)
  const front = screen.getByRole('button', { name: 'Front' })
  expect(front).toHaveAttribute('aria-pressed', 'true')
  expect(
    screen.getByRole('img', { name: /^Copenhagen plank from the front, start: On your side/ }),
  ).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Side' }))
  expect(screen.getByRole('button', { name: 'Side' })).toHaveAttribute('aria-pressed', 'true')
  expect(front).toHaveAttribute('aria-pressed', 'false')
  expect(
    screen.getByRole('img', { name: /^Copenhagen plank from the side, end: Hips up/ }),
  ).toBeVisible()
  expect(screen.getByRole('group', { name: 'Seen from' })).toBeInTheDocument()
})

test('a figure with one view has no view switch', () => {
  motion(true)
  render(<Figure slug="glute-bridge" name="Glute bridge" />)
  expect(screen.queryByRole('group', { name: 'Seen from' })).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Glute bridge, start/ })).toBeVisible()
})

test('a still from the front draws the front view', () => {
  render(<FigureAt slug="copenhagen-plank" t={1} label="Top" view="front" />)
  expect(screen.getByRole('img', { name: 'Top' })).toHaveAttribute('viewBox', '-76 -70 158 130')
})

test('a calf raise shows the foot on the step close up, and where it is', () => {
  render(<FigureAt slug="calf-raise" t={0} label="Calf raise" />)
  const drawing = screen.getByRole('img', { name: 'Calf raise' })
  expect(drawing.querySelector('clipPath circle')).toHaveAttribute('r', '42')
  const plain = render(<FigureAt slug="push-up" t={0} label="Push-up" />)
  expect(plain.container.querySelector('clipPath')).toBeNull()
})
