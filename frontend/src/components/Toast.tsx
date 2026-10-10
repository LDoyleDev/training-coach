/**
 * The answer to an action, shown where it can be seen: pinned above the bottom tab bar (or at
 * the bottom on a wide screen) instead of at the top of a long page. Close it, or it is
 * replaced by the next one.
 */
export default function Toast({ text, onClose }: { text: string | null; onClose: () => void }) {
  if (!text) return null
  return (
    <div
      role="status"
      className="fixed inset-x-3 bottom-20 z-30 mx-auto flex max-w-xl items-start gap-3 rounded-2xl border-2 border-[var(--ink)] bg-[var(--paper)] p-3 shadow-lg sm:bottom-6"
    >
      <p className="m-0 flex-1">{text}</p>
      <button type="button" onClick={onClose} aria-label="Close" className="min-h-9 px-3">
        ×
      </button>
    </div>
  )
}
