/**
 * The body map's two figures (program-builder.md F): a front and a back mannequin, each muscle a
 * region coloured by its band. Drawn on a 120 × 260 box; each shape is the figure's left half
 * and is mirrored across x = 60 for the right, so both sides always match.
 */

export const WIDTH = 120
export const HEIGHT = 260

export type View = 'front' | 'back'

export type Region = { muscle: string; d: string }

/** The mannequin under the regions: head, neck, torso, arms, legs (left halves but the head). */
export const HEAD = { cx: 60, cy: 20, r: 13 }
export const SILHOUETTE: readonly string[] = [
  'M53 31 L60 31 L60 46 L52 46 Z', // neck
  'M60 42 L44 44 Q30 46 28 54 L32 70 L38 118 L35 136 L60 140 Z', // torso
  'M28 50 Q20 54 20 66 L22 100 L32 100 L34 64 Z', // upper arm
  'M22 102 L19 140 L26 152 L31 140 L32 102 Z', // forearm
  'M18 150 Q17 162 23 166 Q29 162 28 150 Z', // hand
  'M35 134 Q33 150 37 196 L56 196 Q60 160 60 140 Z', // thigh
  'M38 200 Q35 222 40 246 L52 246 Q57 222 56 200 Z', // shin
  'M40 246 L52 246 L54 254 L36 254 Z', // foot
]

const SIDE_DELTS = 'M28 50 Q22 54 22 64 L26 66 Q26 58 31 52 Z'
const FOREARMS = 'M22 104 L20 136 L26 140 L31 104 Z'

export const FRONT: readonly Region[] = [
  { muscle: 'neck', d: 'M54 33 L60 35 L60 43 L53 42 Z' },
  { muscle: 'upper traps', d: 'M52 39 Q44 42 38 45 L46 46 L53 44 Z' },
  { muscle: 'front delts', d: 'M38 46 Q30 47 28 55 L31 64 Q34 55 41 50 Z' },
  { muscle: 'side delts', d: SIDE_DELTS },
  { muscle: 'chest', d: 'M59 50 L44 51 Q37 56 37 66 Q43 74 59 72 Z' },
  { muscle: 'biceps', d: 'M27 68 Q23 76 24 96 L31 96 Q33 80 32 70 Z' },
  { muscle: 'forearms', d: FOREARMS },
  { muscle: 'abs', d: 'M59 76 L49 76 L48 116 L59 120 Z' },
  { muscle: 'obliques', d: 'M46 75 L38 73 L40 112 L46 116 Z' },
  { muscle: 'hip flexors', d: 'M44 122 L55 131 L53 139 L41 131 Z' },
  { muscle: 'quads', d: 'M38 140 Q37 165 40 192 L53 192 Q56 166 52 142 Z' },
  { muscle: 'adductors', d: 'M54 142 L59 142 L59 170 L55 186 Z' },
  { muscle: 'tibialis', d: 'M40 204 Q38 220 41 240 L45 240 Q46 220 45 204 Z' },
]

export const BACK: readonly Region[] = [
  { muscle: 'neck', d: 'M54 31 L60 31 L60 41 L53 41 Z' },
  { muscle: 'upper traps', d: 'M53 38 Q42 42 33 46 L44 50 L60 54 L60 43 Z' },
  { muscle: 'rear delts', d: 'M33 47 Q26 50 26 59 L31 61 Q34 54 40 50 Z' },
  { muscle: 'side delts', d: SIDE_DELTS },
  { muscle: 'upper back', d: 'M59 57 L45 53 L43 64 L59 80 Z' },
  { muscle: 'lats', d: 'M41 66 L35 62 Q36 90 46 110 L52 100 Q45 86 50 76 Z' },
  { muscle: 'triceps', d: 'M26 64 Q21 76 22 96 L30 98 Q32 80 31 64 Z' },
  { muscle: 'forearms', d: FOREARMS },
  { muscle: 'lower back', d: 'M59 86 L52 90 L50 116 L59 120 Z' },
  { muscle: 'glutes', d: 'M59 122 L42 124 Q34 134 37 150 Q48 158 59 152 Z' },
  { muscle: 'hamstrings', d: 'M38 156 Q37 175 41 194 L56 194 Q58 172 57 158 Z' },
  { muscle: 'calves', d: 'M39 204 Q35 218 40 236 L54 236 Q58 218 55 204 Z' },
]

export const REGIONS: Record<View, readonly Region[]> = { front: FRONT, back: BACK }

/** The transform that draws a left half as the right. */
export const MIRROR = `translate(${WIDTH} 0) scale(-1 1)`
