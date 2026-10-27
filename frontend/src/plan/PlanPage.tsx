import PlanView from '../App'
import AppShell from '../components/AppShell'
import ExtraCardio from './ExtraCardio'
import Levels from './Levels'

/** /plan: the plan as its own page in the nav (ADR-0069; it was a tab of Progress). Your level on
 * each ladder comes first, where every "Ready to move up" link lands (ADR-0075); then extra cardio
 * a week, which adds to the cardio targets the sessions set (ADR-0079). */
export default function PlanPage() {
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Plan</h1>
      <Levels />
      <ExtraCardio />
      <PlanView />
    </AppShell>
  )
}
