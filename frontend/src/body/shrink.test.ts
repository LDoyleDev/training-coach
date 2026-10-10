import { afterEach, expect, test, vi } from 'vitest'
import { shrink } from './shrink'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function camera(width: number, height: number) {
  const close = vi.fn()
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width, height, close })),
  )
  return close
}

test('a large photo is shrunk to 1600 px on its longest side and re-encoded as JPEG', async () => {
  const close = camera(4000, 3000)
  const drawn: number[][] = []
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: (_: unknown, x: number, y: number, w: number, h: number) => drawn.push([x, y, w, h]),
  } as unknown as CanvasRenderingContext2D)
  const types: string[] = []
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((done, type) => {
    types.push(String(type))
    done(new Blob(['jpeg'], { type: 'image/jpeg' }))
  })
  const out = await shrink(new Blob(['raw']))
  expect(out.type).toBe('image/jpeg')
  expect(drawn).toEqual([[0, 0, 1600, 1200]])
  expect(types).toEqual(['image/jpeg'])
  expect(close).toHaveBeenCalled()
})

test('a small photo keeps its size', async () => {
  camera(800, 600)
  const drawn: number[][] = []
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: (_: unknown, x: number, y: number, w: number, h: number) => drawn.push([x, y, w, h]),
  } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((done) => done(null))
  await expect(shrink(new Blob(['raw']))).rejects.toThrow('No picture')
  expect(drawn).toEqual([[0, 0, 800, 600]])
})

test('a browser that cannot draw says so', async () => {
  camera(800, 600)
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  await expect(shrink(new Blob(['raw']))).rejects.toThrow('cannot resize')
})
