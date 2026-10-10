/** The longest side a photo is shrunk to before upload: plenty for comparing over time. */
export const LONGEST_SIDE = 1600

/** Shrink and re-encode a picture as JPEG in the browser. Re-encoding drops its metadata (the
 * camera's location and time); the server removes any that are left (ADR-0039). */
export async function shrink(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  const scale = Math.min(1, LONGEST_SIDE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  const context = canvas.getContext('2d')
  if (context === null) throw new Error('This browser cannot resize pictures.')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('No picture'))),
      'image/jpeg',
      0.85,
    ),
  )
}
