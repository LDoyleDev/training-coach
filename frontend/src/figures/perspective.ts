/**
 * The front view drawn in perspective (ADR-0063, addendum): the body from front.ts stands in a
 * vertical plane, its chest towards +z, and a camera looks at it from in front of the chest,
 * past the head, so the body runs away from you towards the feet. Far things are smaller and
 * drawn first. World units are cm, y up, the floor at y = 0.
 */
import { solveFront, type FrontLimbJoints, type FrontPose } from './front'
import { SIZE, ball, limb, type Shape, type Tone } from './shapes'
import type { Vec } from './body'

export type Vec3 = readonly [number, number, number]

/** Where the camera is, the point it looks at, and its scale: 1 cm at that point draws as 1. */
export interface Camera {
  at: Vec3
  look: Vec3
}

/** A bench or chair seat seen in the round: its length along x, ``depth`` across z. */
export interface Bench3 {
  x0: number
  x1: number
  top: number
  depth: number
}

/** A cable from a pulley (on a column behind it) to the left or right hand. */
export interface Cable3 {
  pulley: Vec3
  hand: 'L' | 'R'
}

/** What stands around a figure seen from the front: ``standing`` puts it on a floor of its own
 * (no forearm on the floor, as in a side plank), and ``cables`` run to its hands. */
export interface Kit {
  standing?: boolean
  cables?: readonly Cable3[]
}

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const norm = (a: Vec3): Vec3 => {
  const l = Math.hypot(...a)
  return [a[0] / l, a[1] / l, a[2] / l]
}
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]

export interface Seen {
  p: Vec // on the picture, y up
  scale: number // how big 1 cm there is drawn
  depth: number // distance in front of the camera
}

/** A projection for ``camera``. */
export function lens(camera: Camera) {
  const forward = norm(sub(camera.look, camera.at))
  const right = norm(cross(forward, [0, 1, 0]))
  const up = cross(right, forward)
  const focal = dot(sub(camera.look, camera.at), forward)
  return (p: Vec3): Seen => {
    const d = sub(p, camera.at)
    const depth = dot(d, forward)
    const scale = focal / depth
    return { p: [dot(d, right) * scale, dot(d, up) * scale], scale, depth }
  }
}

type Project = ReturnType<typeof lens>

/** Where a point of a body laid face down (``FrontPose.lie``) is: its plane turned about the x
 * axis, the chest (+z) to the floor and the head (+y) towards the camera. */
export function layDown([x, y, z]: Vec3, { slope, lift }: NonNullable<FrontPose['lie']>): Vec3 {
  const [c, s] = [Math.cos((slope * Math.PI) / 180), Math.sin((slope * Math.PI) / 180)]
  return [x, lift + y * s - z * c, y * c + z * s]
}
const laid =
  (world: Project, lie: NonNullable<FrontPose['lie']>): Project =>
  (p) =>
    world(layDown(p, lie))
interface Drawn {
  depth: number
  shapes: Shape[]
}

function capsule(see: Project, a: Vec3, b: Vec3, r: readonly number[], tone: Tone): Drawn {
  const [pa, pb] = [see(a), see(b)]
  return {
    depth: (pa.depth + pb.depth) / 2,
    shapes: [limb(pa.p, pb.p, [r[0] * pa.scale, r[1] * pb.scale], tone)],
  }
}
function sphere(see: Project, c: Vec3, r: number, tone: Tone, nearer = 0): Drawn {
  const pc = see(c)
  return { depth: pc.depth - nearer, shapes: [ball(pc.p, r * pc.scale, tone)] }
}

/** The outline round some spheres, as one shape: a trunk part wider than it is deep. */
function hull(see: Project, spheres: readonly [Vec3, number][], tone: Tone): Drawn {
  const points: Vec[] = []
  let depth = 0
  for (const [c, r] of spheres) {
    const pc = see(c)
    depth += pc.depth / spheres.length
    for (let i = 0; i < 20; i++) {
      const a = (i / 20) * 2 * Math.PI
      points.push([pc.p[0] + r * pc.scale * Math.cos(a), pc.p[1] + r * pc.scale * Math.sin(a)])
    }
  }
  return { depth, shapes: [{ kind: 'path', d: path(convex(points)), tone }] }
}

/** The convex hull of ``points`` (monotone chain). */
function convex(points: Vec[]): Vec[] {
  const ps = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const turn = (o: Vec, a: Vec, b: Vec) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const half = (list: Vec[]) => {
    const out: Vec[] = []
    for (const p of list) {
      while (out.length >= 2 && turn(out[out.length - 2], out[out.length - 1], p) <= 0) out.pop()
      out.push(p)
    }
    return out.slice(0, -1)
  }
  return [...half(ps), ...half([...ps].reverse())]
}

const n = (v: number) => Number(v.toFixed(2))
const path = (points: readonly Vec[]) =>
  `M ${points.map((p) => `${n(p[0])} ${n(-p[1])}`).join(' L ')} Z`

function face(see: Project, corners: readonly Vec3[], tone: Tone, bias = 0): Drawn {
  const seen = corners.map(see)
  const depth = seen.reduce((s, c) => s + c.depth, 0) / seen.length + bias
  return { depth, shapes: [{ kind: 'path', d: path(seen.map((c) => c.p)), tone }] }
}

/** A box from ``lo`` to ``hi``: the faces turned towards the camera. */
function box(see: Project, camera: Camera, lo: Vec3, hi: Vec3, tone: Tone, bias = 0): Drawn[] {
  const [x0, y0, z0] = lo
  const [x1, y1, z1] = hi
  const out: Drawn[] = []
  const c = camera.at
  if (c[1] > y1)
    out.push(
      face(
        see,
        [
          [x0, y1, z0],
          [x1, y1, z0],
          [x1, y1, z1],
          [x0, y1, z1],
        ],
        tone,
        bias,
      ),
    )
  if (c[2] > z1)
    out.push(
      face(
        see,
        [
          [x0, y0, z1],
          [x1, y0, z1],
          [x1, y1, z1],
          [x0, y1, z1],
        ],
        tone,
        bias,
      ),
    )
  if (c[0] > x1)
    out.push(
      face(
        see,
        [
          [x1, y0, z0],
          [x1, y0, z1],
          [x1, y1, z1],
          [x1, y1, z0],
        ],
        tone,
        bias,
      ),
    )
  // Its own faces in one block, so they don't interleave with the body's parts.
  const depth = Math.min(...out.map((d) => d.depth))
  return [{ depth, shapes: out.flatMap((d) => d.shapes) }]
}

function bench(see: Project, camera: Camera, b: Bench3): Drawn[] {
  const z = b.depth / 2
  const leg = (x: number, zz: number) =>
    box(see, camera, [x - 2.5, 0, zz - 2.5], [x + 2.5, b.top - 6, zz + 2.5], 'prop')
  return [
    ...leg(b.x0 + 4, -z + 4),
    ...leg(b.x1 - 4, -z + 4),
    ...leg(b.x0 + 4, z - 4),
    ...leg(b.x1 - 4, z - 4),
    // The seat goes under whatever rests on it.
    ...box(see, camera, [b.x0, b.top - 6, -z], [b.x1, b.top, z], 'prop', 60),
  ]
}

const at = (p: Vec, z = 0): Vec3 => [p[0], p[1], z]

function arm(see: Project, j: FrontLimbJoints, tone: Tone, forearm?: Vec3[]): Drawn[] {
  const [wrist, tip] = forearm ?? [at(j.end, j.z[1]), at(j.tip, j.z[1])]
  const elbow = at(j.mid, j.z[0])
  return [
    capsule(see, at(j.root), elbow, SIZE.upperArm, tone),
    capsule(see, elbow, wrist, SIZE.forearm, tone),
    capsule(see, wrist, tip, SIZE.hand, tone),
    sphere(see, wrist, SIZE.joint.wrist, tone, 0.5),
    sphere(see, elbow, SIZE.joint.elbow, tone, 0.5),
    sphere(see, at(j.root), SIZE.joint.shoulder, tone, 0.5),
  ]
}

function leg(see: Project, j: FrontLimbJoints, tone: Tone): Drawn[] {
  // Toes point the way the chest faces.
  const toe: Vec3 = [j.end[0], j.end[1] - 1, 13]
  return [
    capsule(see, at(j.root), at(j.mid), SIZE.thigh, tone),
    capsule(see, at(j.mid), at(j.end), SIZE.shin, tone),
    capsule(see, at(j.end), toe, [3.8, 3.2], tone),
    sphere(see, at(j.end), SIZE.joint.ankle, tone, 0.5),
    sphere(see, at(j.mid), SIZE.joint.knee, tone, 0.5),
  ]
}

/** A cable column behind each pulley, its stack at the foot, and the cable to the hand. */
function cables(see: Project, camera: Camera, j: ReturnType<typeof solveFront>, kit: Kit) {
  return (kit.cables ?? []).flatMap(({ pulley: [x, y, z], hand }): Drawn[] => {
    const limb = hand === 'L' ? j.armL : j.armR
    const grip = at(limb.tip, limb.z[1])
    return [
      ...box(see, camera, [x - 4, 0, z - 12], [x + 4, Math.max(y + 8, 150), z - 4], 'bell'),
      ...box(see, camera, [x - 10, 0, z - 18], [x + 10, 45, z + 2], 'bell'),
      sphere(see, [x, y, z], 4.5, 'far'),
      capsule(see, [x, y, z], grip, [1.1, 1.1], 'far'),
      sphere(see, grip, 3, 'bell', 2),
    ]
  })
}

/** Everything to draw for ``pose`` seen by ``camera``, far to near. */
export function perspectiveShapes(
  pose: FrontPose,
  camera: Camera,
  seat?: Bench3,
  kit: Kit = {},
): Shape[] {
  const world = lens(camera)
  const see = pose.lie ? laid(world, pose.lie) : world
  const j = solveFront(pose)
  const [hipL, hipR] = [at(j.legL.root), at(j.legR.root)]
  const [shL, shR] = [at(j.armL.root), at(j.armR.root)]
  const waistL = at([(j.legL.root[0] + j.armL.root[0]) / 2, (j.legL.root[1] + j.armL.root[1]) / 2])
  const waistR = at([(j.legR.root[0] + j.armR.root[0]) / 2, (j.legR.root[1] + j.armR.root[1]) / 2])
  // The bottom forearm lies on the floor, pointing the way the chest faces.
  const elbow = j.armL.mid
  const forearm: Vec3[] | undefined = kit.standing
    ? undefined
    : [
        [elbow[0] + 1, 3, 22],
        [elbow[0] + 1.5, 2.4, 30],
      ]
  const nose: Vec3 = [j.head[0], j.head[1], 9.5]
  const [x0, x1] = pose.lie ? [-80, 80] : kit.standing ? [-60, 60] : [-75, 48]
  const [z0, z1] = pose.lie ? [-10, 180] : [-32, 42] // lying, the mat runs away from you
  const mat: Vec3[] = [
    [x0, 0, z0],
    [x1, 0, z0],
    [x1, 0, z1],
    [x0, 0, z1],
  ]
  const edges: Shape[] = [{ kind: 'floor', d: path(mat.map((c) => world(c).p)) }]
  const parts: Drawn[] = [
    ...(seat ? bench(see, camera, seat) : []),
    ...cables(see, camera, j, kit),
    ...leg(see, j.legL, 'far'),
    ...leg(see, j.legR, 'near'),
    ...arm(see, j.armL, 'far', forearm),
    hull(
      see,
      [
        [hipL, 10],
        [hipR, 10],
        [waistL, 9],
        [waistR, 9],
      ],
      'near',
    ),
    hull(
      see,
      [
        [waistL, 9],
        [waistR, 9],
        [shL, 8.5],
        [shR, 8.5],
      ],
      'near',
    ),
    capsule(see, at(j.neckBase), at(j.neckTop), SIZE.neck, 'near'),
    sphere(see, at(j.head), 10.5, 'near'),
    sphere(see, nose, 1.9, 'near', -0.1),
    ...arm(see, j.armR, 'near'),
  ]
  return [...edges, ...parts.sort((a, b) => b.depth - a.depth).flatMap((d) => d.shapes)]
}
