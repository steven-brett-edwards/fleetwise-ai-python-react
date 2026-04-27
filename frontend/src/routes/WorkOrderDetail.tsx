import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import clsx from 'clsx'
import { useVehicle, useWorkOrder } from '../hooks/useFleetData'
import Spinner from '../components/Spinner'
import StatusPill from '../components/StatusPill'

export default function WorkOrderDetail() {
  const params = useParams<{ id: string }>()
  const id = params.id ? Number(params.id) : null
  const idValid = id !== null && Number.isFinite(id)

  const woQ = useWorkOrder(idValid ? id : null)
  const vehicleQ = useVehicle(woQ.data?.vehicleId ?? null)

  if (!idValid) return <NotFound />
  if (woQ.isLoading) return <Spinner label="Loading work order…" />
  if (woQ.isError || !woQ.data) return <NotFound />

  const wo = woQ.data
  const v = vehicleQ.data

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <Link
          to="/work-orders"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to work orders
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-sm font-mono text-[var(--color-accent)]">{wo.workOrderNumber}</div>
          <h1 className="text-2xl font-semibold mt-1">{wo.description}</h1>
          {v ? (
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              Vehicle:{' '}
              <Link
                to={`/vehicles/${v.id}`}
                className="text-[var(--color-accent)] hover:underline"
              >
                {v.assetNumber} — {v.year} {v.make} {v.model}
              </Link>
            </p>
          ) : null}
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusPill value={wo.status} kind="workOrder" />
          <StatusPill value={wo.priority} kind="priority" />
        </div>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Field label="Requested" value={formatDate(wo.requestedDate)} />
        <Field
          label="Completed"
          value={wo.completedDate ? formatDate(wo.completedDate) : '—'}
        />
        <Field label="Technician" value={wo.assignedTechnician ?? '—'} />
        <Field
          label="Labor hours"
          value={wo.laborHours !== null ? wo.laborHours.toFixed(2) : '—'}
        />
        <Field
          label="Total cost"
          value={wo.totalCost !== null ? formatCurrency(wo.totalCost) : '—'}
        />
      </section>

      {wo.notes ? (
        <section className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm">
          <div className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
            Notes
          </div>
          {wo.notes}
        </section>
      ) : null}
    </div>
  )
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">{label}</div>
      <div className={clsx('mt-1 text-sm', mono && 'font-mono')}>{value}</div>
    </div>
  )
}

function NotFound() {
  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-2xl font-semibold">Work order not found</h1>
      <p className="text-sm text-[var(--color-text-muted)]">
        That work-order ID doesn't exist.
      </p>
      <Link to="/work-orders" className="text-sm text-[var(--color-accent)] hover:underline">
        ← Back to work orders
      </Link>
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
