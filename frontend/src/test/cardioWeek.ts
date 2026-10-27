import type { CardioOptions } from '../api'

type Week = CardioOptions['week']
type Over = Partial<Omit<Week, 'zones'>> & { zones?: Partial<Week['zones']> }

/** The Cardio week with nothing logged and no targets; tests override what they're about. */
export const emptyWeek = ({ zones, ...over }: Over = {}): Week => ({
  zone2: 0,
  moderate: 0,
  zone2_target: null,
  zone2_left: null,
  total: 0,
  total_target: null,
  total_left: null,
  ...over,
  zones: {
    below_zone1: 0,
    zone1: 0,
    zone2: 0,
    zone3: 0,
    zone4: 0,
    zone5: 0,
    zone2_no_hr: 0,
    zone3_up_no_hr: 0,
    ...zones,
  },
})
