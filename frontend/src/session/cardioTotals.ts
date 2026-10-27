/** What the last 7 days of cardio say in words (ADR-0079). */
import type { CardioOptions } from '../api'

export type CardioWeekView = CardioOptions['week']
type Zones = CardioWeekView['zones']

/** " of 45–75", or nothing without a target. */
export const range = (target: readonly number[] | null | undefined): string =>
  target ? ` of ${target[0]}–${target[1]}` : ''

/** What's left to the low end of a target: "10 min left", or "on target" from there up. Over
 * the range is fine, so it never says more than that (ADR-0079). Null without a target. */
export function standing(left: number | null | undefined): string | null {
  if (left === null || left === undefined) return null
  return left > 0 ? `${left} min left` : 'on target'
}

type Row = { label: string; minutes: number; note: string | null; measured: boolean }

/** The zones that have minutes, easiest first: what the band's heart rate showed, and minutes
 * without heart rate in the zone they were logged as (ADR-0079). */
export function zoneRows(zones: Zones): Row[] {
  const rows: Row[] = [
    { label: 'Easy (below zone 1)', minutes: zones.below_zone1, note: null, measured: true },
    { label: 'Zone 1', minutes: zones.zone1, note: null, measured: true },
    {
      label: 'Zone 2',
      minutes: zones.zone2 + zones.zone2_no_hr,
      note: zones.zone2_no_hr > 0 ? `${zones.zone2_no_hr} without heart rate` : null,
      measured: zones.zone2 > 0,
    },
    { label: 'Zone 3', minutes: zones.zone3, note: null, measured: true },
    { label: 'Zone 4', minutes: zones.zone4, note: null, measured: true },
    { label: 'Zone 5', minutes: zones.zone5, note: null, measured: true },
    {
      label: 'Zone 3+ (no heart rate)',
      minutes: zones.zone3_up_no_hr,
      note: 'logged as moderate',
      measured: false,
    },
  ]
  return rows.filter((r) => r.minutes > 0)
}
