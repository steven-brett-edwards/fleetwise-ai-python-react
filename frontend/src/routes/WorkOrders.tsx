import { Link, useSearchParams } from 'react-router-dom'
import { useWorkOrders } from '../hooks/useFleetData'
import Spinner from '../components/Spinner'
import StatusPill from '../components/StatusPill'

const STATUS_OPTIONS = ['', 'Open', 'InProgress', 'Completed', 'Cancelled']

export default function WorkOrders() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? undefined
  const { data, isLoading, isError } = useWorkOrders({ status })

  function setFilter(value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set('status', value)
    else next.delete('status')
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold">Work orders</h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Filter by status. Click a number for full detail.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
          Status
          <select
            value={status ?? ''}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-[var(--color-text)] normal-case px-3 py-2 focus:outline-none focus:border-[var(--color-accent)]"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt === '' ? 'All' : opt}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <Spinner label="Loading work orders…" />
      ) : isError ? (
        <div className="rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 text-[var(--color-danger)] px-3 py-2 text-sm">
          Couldn't load work orders.
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface-raised)]">
              <tr>
                <th className="text-left px-4 py-3">Number</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Priority</th>
                <th className="text-left px-4 py-3">Description</th>
                <th className="text-left px-4 py-3">Technician</th>
                <th className="text-left px-4 py-3">Requested</th>
                <th className="text-right px-4 py-3">Cost</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((wo) => (
                <tr
                  key={wo.id}
                  className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-raised)]/40"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/work-orders/${wo.id}`}
                      className="font-medium text-[var(--color-accent)] hover:underline"
                    >
                      {wo.workOrderNumber}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill value={wo.status} kind="workOrder" />
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill value={wo.priority} kind="priority" />
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{wo.description}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">
                    {wo.assignedTechnician ?? '—'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{formatDate(wo.requestedDate)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {wo.totalCost !== null ? formatCurrency(wo.totalCost) : '—'}
                  </td>
                </tr>
              ))}
              {data && data.length === 0 ? (
                <tr>
                  <td
                    className="px-4 py-8 text-center text-[var(--color-text-muted)]"
                    colSpan={7}
                  >
                    No work orders match this filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatCurrency(n: number): string {
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
}
