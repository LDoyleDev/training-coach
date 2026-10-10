import { useEffect, useState } from 'react'
import {
  deletePhoto,
  fetchPhotos,
  SignedOutError,
  uploadPhoto,
  type PhotoView,
  type Pose,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { isoDay } from './logic'
import { shrink } from './shrink'
import { card, small } from '../ui'

const POSES: { pose: Pose; label: string }[] = [
  { pose: 'front', label: 'Front' },
  { pose: 'side', label: 'Side' },
  { pose: 'back', label: 'Back' },
]

/** Photos are taken now, so they are today's. */
const today = () => isoDay(new Date())

const pick =
  'flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded-xl border-2 border-[var(--ink)] px-3 font-bold text-[var(--ink)]'

/** Progress photos on /body (2-B, #143): take or choose one per pose, see them by day.
 * Personal: only ever shown to the signed-in owner. */
export default function Photos() {
  const [photos, setPhotos] = useState<PhotoView[] | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState<Pose | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [confirming, setConfirming] = useState<number | null>(null) // asked "Remove?"

  const fail = (error: unknown, otherwise: string) => {
    if (error instanceof SignedOutError) setSignedOut(true)
    else setNote(otherwise)
  }

  const load = () =>
    fetchPhotos()
      .then(setPhotos)
      .catch((error: unknown) => fail(error, "Couldn't load your photos."))
  useEffect(() => {
    void load()
  }, [])

  const upload = async (pose: Pose, file: File | undefined) => {
    if (!file) return
    setBusy(pose)
    setNote(null)
    setSignedOut(false)
    let small: Blob
    try {
      small = await shrink(file)
    } catch {
      // Not a connection problem: retrying the same picture won't help.
      setNote("That picture can't be read here. Try a photo from the camera (JPEG).")
      setBusy(null)
      return
    }
    try {
      const answer = await uploadPhoto(today(), pose, small)
      if (answer === true) {
        setNote('Photo saved.')
        await load()
      } else setNote(answer)
    } catch (error) {
      fail(error, "Couldn't save the photo. Check your connection and try again.")
    } finally {
      setBusy(null)
    }
  }

  const remove = async (photo: PhotoView) => {
    setConfirming(null)
    setNote(null)
    setSignedOut(false)
    try {
      await deletePhoto(photo.id)
      await load()
    } catch (error) {
      fail(error, "Couldn't remove it. Check your connection and try again.")
    }
  }

  const days = [...new Set((photos ?? []).map((p) => p.on))]

  return (
    <section aria-labelledby="photos" className={card + ' flex flex-col gap-3'}>
      <h2 id="photos" className="text-lg font-bold">
        Photos
      </h2>
      <p className="text-[var(--slate)]">
        Same place, light and time of day each time, so they compare. Only you can see them; the
        camera's location is removed.
      </p>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
      <div className="flex gap-2">
        {POSES.map(({ pose, label }) => (
          <label key={pose} className={pick}>
            {busy === pose ? 'Saving…' : `${label} today`}
            <input
              type="file"
              accept="image/*"
              className="sr-only"
              aria-label={`${label} photo for today`}
              disabled={busy !== null}
              onChange={(e) => {
                void upload(pose, e.target.files?.[0])
                e.target.value = '' // the same file again still counts as a change
              }}
            />
          </label>
        ))}
      </div>
      {days.map((on) => (
        <div key={on} className="flex flex-col gap-2">
          <p className="font-bold">{on}</p>
          <div className="grid grid-cols-3 gap-2">
            {(photos ?? [])
              .filter((p) => p.on === on)
              .map((photo) => (
                <figure key={photo.id} className="flex flex-col gap-1">
                  <img
                    src={`/api/photos/${photo.id}`}
                    alt={`${photo.pose} on ${on}`}
                    loading="lazy"
                    className="aspect-[3/4] w-full rounded-xl object-cover"
                  />
                  <figcaption className="flex flex-wrap items-center justify-between gap-1 text-sm">
                    {POSES.find((p) => p.pose === photo.pose)?.label}
                    {confirming === photo.id ? (
                      <span className="flex w-full gap-1">
                        <button
                          type="button"
                          className={small + ' flex-1 px-1'}
                          aria-label={`Keep the ${photo.pose} photo on ${on}`}
                          onClick={() => setConfirming(null)}
                        >
                          Keep
                        </button>
                        <button
                          type="button"
                          className={small + ' flex-1 px-1 text-[var(--bell-ink)]'}
                          aria-label={`Yes, remove the ${photo.pose} photo on ${on}`}
                          onClick={() => remove(photo)}
                        >
                          Remove
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className={small}
                        aria-label={`Remove the ${photo.pose} photo on ${on}`}
                        onClick={() => setConfirming(photo.id)}
                      >
                        ×
                      </button>
                    )}
                  </figcaption>
                </figure>
              ))}
          </div>
        </div>
      ))}
    </section>
  )
}
