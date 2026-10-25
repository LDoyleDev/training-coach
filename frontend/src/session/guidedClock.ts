import { useEffect, useRef, useState } from 'react'
import { unlockAudio } from '../hiit/sounds'
import type { Cue } from './flow'

const TICK_MS = 200
const CATCH_UP = 2 // seconds: after a longer gap (screen locked) only the latest sound plays

export type Stage = 'ready' | 'running' | 'finished'

/** The running clock of a guided timeline, as the mobility flow's player keeps it (ADR-0062):
 * wall-clock time, not tick counts (a phone throttles timers), so pauses, a locked screen and
 * Back or Skip all land where they should. It plays `cuesFor` the time each tick crossed, keeps
 * the screen on while running, and stops by itself at `total`. `active` is the time actually
 * run, pauses and jumps left out: what gets logged. */
export function useGuidedClock(
  total: number,
  cuesFor: (from: number, to: number) => Cue[],
  play: (cue: Cue) => void,
) {
  const [stage, setStage] = useState<Stage>('ready')
  const [paused, setPaused] = useState(false)
  const [t, setT] = useState(0) // where the timeline is, in seconds
  const [ran, setRan] = useState(0) // seconds actually run, once finished

  const banked = useRef(0)
  const since = useRef<number | null>(null)
  const offset = useRef(0)
  const last = useRef(0)
  const active = () =>
    (banked.current + (since.current === null ? 0 : Date.now() - since.current)) / 1000
  const position = () => Math.max(0, offset.current + active())

  const finish = () => {
    const seconds = active()
    banked.current = seconds * 1000
    since.current = null
    setRan(seconds)
    setStage('finished')
  }

  const tick = () => {
    const now = position()
    const due = cuesFor(last.current, now)
    for (const cue of now - last.current > CATCH_UP ? due.slice(-1) : due) play(cue)
    last.current = now
    setT(now)
    if (now >= total) finish()
  }
  const latestTick = useRef(tick)
  useEffect(() => {
    latestTick.current = tick
  })

  useEffect(() => {
    if (stage !== 'running' || paused) return
    const id = setInterval(() => latestTick.current(), TICK_MS)
    const onVisible = () => latestTick.current()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [stage, paused])

  // Keep the screen on while it runs, asking again when the page is visible (as the HIIT timer).
  useEffect(() => {
    if (stage !== 'running') return
    let live = true
    let lock: WakeLockSentinel | null = null
    const acquire = () => {
      try {
        navigator.wakeLock
          ?.request('screen')
          .then((next) => {
            if (!live) return void next.release().catch(() => {})
            lock?.release().catch(() => {})
            lock = next
          })
          .catch(() => {})
      } catch {
        // no wake lock here: the timer still runs
      }
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') acquire()
    }
    acquire()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      live = false
      document.removeEventListener('visibilitychange', onVisible)
      lock?.release().catch(() => {})
    }
  }, [stage])

  const begin = () => {
    unlockAudio() // inside the tap: browsers only allow sound after a gesture
    banked.current = 0
    since.current = Date.now()
    offset.current = 0
    last.current = 0
    setT(0)
    setPaused(false)
    setStage('running')
  }

  const pause = () => {
    if (paused) since.current = Date.now()
    else {
      banked.current = active() * 1000
      since.current = null
    }
    setPaused(!paused)
  }

  /** Move to `to` seconds without sounds for the time jumped over or adding to the time run. */
  const jumpTo = (to: number) => {
    offset.current += to - position()
    last.current = to
    setT(to)
    if (to >= total) finish()
  }

  return { stage, paused, t, ran, begin, pause, jumpTo, finish, position }
}
