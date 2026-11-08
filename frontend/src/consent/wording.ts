import type { ConsentCategory } from '../api'

/**
 * The wording version of each category (ADR-0090). It must match ``VERSIONS`` in the backend's
 * ``domain/consent.py`` (a backend test checks): bump both when a category's wording changes,
 * and everyone who said yes is asked again.
 */
export const VERSIONS = {
  body: 1,
  daily_check: 1,
  band: 1,
  walkthrough: 1,
} satisfies Record<ConsentCategory, number>

/** Under every card while the app is a private test (ADR-0090). */
export const DRAFT =
  'Training Coach is a private test for invited family and friends, and this wording is a draft.'

type Wording = {
  name: string // on Account's list
  title: string // the card's question
  text: string // what is kept, why, that it's health data, and withdrawing
  off: string // after "Not now"
  deletes: string // what withdrawing deletes, for its confirm step
}

// Draft wording, from the privacy draft's rows (docs/legal/privacy-policy.md). A lawyer reviews
// it before any public release.
export const WORDING: Record<ConsentCategory, Wording> = {
  body: {
    name: 'Measurements and photos',
    title: 'Keep your measurements and photos?',
    text:
      'Training Coach keeps the measurements you enter (bodyweight, body fat, height, waist, ' +
      'the others, and resting heart rate), your progress photos and your body settings, to ' +
      'show how you’re changing. This is health data, so it’s only kept if you say yes. You ' +
      'can withdraw at any time on Account, and withdrawing deletes all of it.',
    off: 'Measurements and photos stay off, and nothing is kept.',
    deletes:
      'every measurement and photo, your height and body-fat estimate setting, and your weekly ' +
      'AI comments',
  },
  daily_check: {
    name: 'Daily check',
    title: 'Keep your daily check?',
    text:
      'The daily check asks how you slept, how sore you are and your energy, then suggests ' +
      'training as planned, lighter or resting. Training Coach keeps your answers for a year ' +
      'for that advice. This is health data, so it’s only kept if you say yes. You can ' +
      'withdraw at any time on Account, and withdrawing deletes every answer.',
    off: 'The daily check stays off, and nothing is kept.',
    deletes: 'every daily check answer, and your weekly AI comments',
  },
  band: {
    name: 'Band data and heart rate',
    title: 'Keep your band data and heart rate?',
    text:
      'Training Coach keeps what your phone sends from your band (workouts with heart rate, ' +
      'sleep, steps, resting heart rate and weight), the heart rates you type in for cardio ' +
      'and your heart-rate settings. It uses them to count cardio once you confirm, work out ' +
      'your heart-rate zones and show your sleep and steps. This is health data, so it’s only ' +
      'kept if you say yes. You can withdraw at any time on Account, and withdrawing deletes ' +
      'all of it.',
    off: 'Band data and heart rate stay off, and nothing is kept.',
    deletes:
      'all band data (workouts, heart rate, sleep and steps), the phone’s secret, the heart ' +
      'rates on your cardio logs and your own max heart rate',
  },
  walkthrough: {
    name: 'Walk-through answers',
    title: 'Keep your walk-through answers?',
    text:
      'The walk-through asks your age, how you exercise now, what you can do, and your days, ' +
      'minutes and kit, to build your plan. Training Coach keeps the answers to adjust it ' +
      'later. Some are health data, so they’re only kept if you say yes. You can withdraw at ' +
      'any time on Account, and withdrawing deletes the answers; the plan made from them stays.',
    off: 'Your walk-through answers aren’t kept.',
    deletes: 'your walk-through answers. The plan made from them stays',
  },
}
