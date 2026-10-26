import Figure from '../figures/Figure'
import { FIGURES } from '../figures/poses'

/** How the exercise moves, under its how-to on the set screen: the mannequin (ADR-0063), for an
 * exercise that has one, set up as its ladder ``step`` says. Always shown; the counter sits
 * above it, so it never pushes the counter out of view. */
export default function Movement({
  slug,
  name,
  step,
}: {
  slug: string
  name: string
  step?: string
}) {
  if (!(slug in FIGURES)) return null
  return <Figure slug={slug} name={name} step={step} />
}
