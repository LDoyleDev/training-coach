import PlanView from '../App'
import AppShell from '../components/AppShell'

/** /plan: the plan as its own page in the nav (ADR-0069; it was a tab of Progress). */
export default function PlanPage() {
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Plan</h1>
      <PlanView />
    </AppShell>
  )
}
