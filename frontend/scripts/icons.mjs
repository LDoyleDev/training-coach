// Draws the app icons (public/icons/*.png) from the favicon's mark: the kettlebell handle in ink
// over the pink bell, on chalk. No dependencies: shapes are sampled 4x4 per pixel and written
// as PNG with node's zlib. Run `node scripts/icons.mjs` after changing the mark; commit the PNGs.
import { mkdirSync, writeFileSync } from 'node:fs'
import { deflateSync } from 'node:zlib'

const CHALK = [0xf1, 0xf2, 0xef]
const INK = [0x22, 0x28, 0x2d]
const BELL = [0xd4, 0x4d, 0x7a]
const OUT = new URL('../public/icons/', import.meta.url)

// favicon.svg in its own 32-unit box: the handle is the top half of a circle at (16, 13),
// radius 6, stroke 3.2 with round caps; the bell is a circle at (16, 20), radius 9.
function markAt(x, y) {
  if (Math.hypot(x - 16, y - 20) <= 9) return BELL
  const handle =
    y <= 13
      ? Math.abs(Math.hypot(x - 16, y - 13) - 6)
      : Math.min(Math.hypot(x - 10, y - 13), Math.hypot(x - 22, y - 13))
  return handle <= 1.6 ? INK : null
}

/**
 * A square icon `size` px wide. The mark (about 18 x 24 units, centred near y = 17) fills
 * `scale` of the side; `radius` rounds the corners (0 = full bleed, for maskable and Apple).
 */
function draw(size, scale, radius) {
  const unit = (size * scale) / 24 // the mark's height maps to scale * size
  const px = new Uint8Array(size * size * 4)
  const N = 4
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      const sum = [0, 0, 0, 0]
      for (let sj = 0; sj < N; sj++) {
        for (let si = 0; si < N; si++) {
          const x = i + (si + 0.5) / N
          const y = j + (sj + 0.5) / N
          if (radius > 0) {
            const cx = Math.min(Math.max(x, radius), size - radius)
            const cy = Math.min(Math.max(y, radius), size - radius)
            if (Math.hypot(x - cx, y - cy) > radius) continue // outside the rounded corner
          }
          const colour = markAt(16 + (x - size / 2) / unit, 17.2 + (y - size / 2) / unit) ?? CHALK
          sum[0] += colour[0]
          sum[1] += colour[1]
          sum[2] += colour[2]
          sum[3] += 255
        }
      }
      const n = N * N
      const covered = sum[3] / 255
      const o = (j * size + i) * 4
      for (let c = 0; c < 3; c++) px[o + c] = covered ? Math.round(sum[c] / covered) : 0
      px[o + 3] = Math.round(sum[3] / n)
    }
  }
  return png(size, px)
}

const CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})

function crc32(buf) {
  let c = 0xffffffff
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const head = Buffer.alloc(8)
  head.writeUInt32BE(data.length, 0)
  head.write(type, 4, 'ascii')
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), data])), 0)
  return Buffer.concat([head, data, crc])
}

function png(size, rgba) {
  const raw = Buffer.alloc((size * 4 + 1) * size)
  for (let j = 0; j < size; j++) {
    raw[j * (size * 4 + 1)] = 0 // no filter
    Buffer.from(rgba.buffer, j * size * 4, size * 4).copy(raw, j * (size * 4 + 1) + 1)
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr.set([8, 6, 0, 0, 0], 8) // 8-bit RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

mkdirSync(OUT, { recursive: true })
const icons = {
  'icon-192.png': draw(192, 0.7, 192 * 0.2),
  'icon-512.png': draw(512, 0.7, 512 * 0.2),
  // Maskable: full bleed, the mark inside the central 80% safe circle.
  'icon-maskable-512.png': draw(512, 0.5, 0),
  'apple-touch-icon.png': draw(180, 0.62, 0),
}
for (const [name, data] of Object.entries(icons)) {
  writeFileSync(new URL(name, OUT), data)
  console.log(`${name}: ${data.length} bytes`)
}
