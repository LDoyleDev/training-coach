/** Where a movement's start and end picture goes, keyed by its slug (ADR-0062). The mannequin
 * figures are drawn separately; until they arrive there is nothing to show. */
export default function MovePicture({ slug }: { slug: string }) {
  return <span hidden data-move={slug} />
}
