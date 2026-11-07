import { useState } from 'react'
import Leave from './account/Leave'
import { downloadExport, type Me, StaleSignInError } from './api'
import { card, primaryInline } from './ui'

const longDay = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

/**
 * While the app is closed to members (TC_MULTI_USER off, ADR-0059): every page is this one, the
 * notice on their next sign-in. It says when their data goes, and offers only what still answers
 * them: downloading it, or leaving now.
 */
export function Closing({ me }: { me: Me }) {
  const [note, setNote] = useState<string | null>(null)

  const download = () => {
    setNote('Preparing your data…')
    downloadExport()
      .then((zip) => {
        const url = URL.createObjectURL(zip)
        const link = document.createElement('a')
        link.href = url
        link.download = `training-coach-${new Date().toISOString().slice(0, 10)}.zip`
        link.click()
        URL.revokeObjectURL(url)
        setNote('Your data is downloading.')
      })
      .catch((error: unknown) =>
        setNote(
          error instanceof StaleSignInError
            ? 'For safety, downloading everything needs you to confirm it’s you. Try again and ' +
                'confirm with your fingerprint when your phone asks.'
            : "That didn't work. Check your connection and try again.",
        ),
      )
  }

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 p-4">
      <section aria-labelledby="closing" className={card}>
        <h1 id="closing" className="m-0 mb-3">
          Training Coach is closing to members
        </h1>
        <p className="mt-0">
          {me.closing_on
            ? `Everything of yours will be erased on ${longDay(me.closing_on)}.`
            : 'Everything of yours will be erased 30 days from now.'}{' '}
          Until then you can download your data, or leave now.
        </p>
        <button type="button" className={primaryInline} onClick={download}>
          Download my data
        </button>
        {note && (
          <p role="status" className="mb-0">
            {note}
          </p>
        )}
      </section>
      <Leave />
    </main>
  )
}
