import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import clsx from 'clsx'
import {
  useVehicle,
  useVehicleMaintenance,
  useVehicleWorkOrders,
} from '../hooks/useFleetData'
import Spinner from '../components/Spinner'
import StatusPill from '../components/StatusPill'

type Tab = 'maintenance' | 'work-orders'

export default function VehicleDetail() {
  const params = useParams<{ id: string }>()
  const id = params.id ? Number(params.id) : null
  const idValid = id !== null && Number.isFinite(id)

  const [tab, setTab] = useState<Tab>('maintenance')

  const vehicleQ = useVehicle(idValid ? id : null)
  const maintenanceQ = useVehicleMaintenance(idValid && tab === 'maintenance' ? id : null)
  const workOrdersQ = useVehicleWorkOrders(idValid && tab === 'work-orders' ? id : null)

  if (!idValid) {
    return <NotFound />
  }
  if (vehicleQ.isLoading) return <Spinner label="Loading vehicle…" />
  if (vehicleQ.isError || !vehicleQ.data) return <NotFound />

  const v = vehicleQ.data

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <Link
          to="/vehicles"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to vehicles
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-sm font-mono text-[var(--color-accent)]">{v.assetNumber}</div>
          <h1 className="text-2xl font-semibold mt-1">
            {v.year} {v.make} {v.model}
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            {v.department} · {v.fuelType} · {v.licensePlate}
          </p>
        </div>
        <StatusPill value={v.status} />
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Field label="Mileage" value={v.currentMileage.toLocaleString()} />
        <Field label="VIN" value={v.vin} mono />
        <Field label="Location" value={v.location} />
        <Field label="Driver" value={v.assignedDriver ?? '—'} />
        <Field label="Acquired" value={formatDate(v.acquisitionDate)} />
        <Field label="Acquisition cost" value={formatCurrency(v.acquisitionCost)} />
      </section>

      {v.notes ? (
        <section className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm">
          <div className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
            Notes
          </div>
          {v.notes}
        </section>
      ) : null}

      <div className="border-b border-[var(--color-border)] flex gap-1">
        <TabButton active={tab === 'maintenance'} onClick={() => setTab('maintenance')}>
          Maintenance history
        </TabButton>
        <TabButton active={tab === 'work-orders'} onClick={() => setTab('work-orders')}>
          Work orders
        </TabButton>
      </div>

      {tab === 'maintenance' ? (
        maintenanceQ.isLoading ? (
          <Spinner label="Loading maintenance records…" />
        ) : maintenanceQ.isError ? (
          <ErrorBox>Couldn't load maintenance records.</ErrorBox>
        ) : (maintenanceQ.data ?? []).length === 0 ? (
          <Empty>No maintenance records on file.</Empty>
        ) : (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface-raised)]">
                <tr>
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-left px-4 py-3">Description</th>
                  <th className="text-left px-4 py-3">Technician</th>
                  <th className="text-right px-4 py-3">Mileage</th>
                  <th className="text-right px-4 py-3">Cost</th>
                </tr>
              </thead>
              <tbody>
                {maintenanceQ.data!.map((r) => (
                  <tr
                    key={r.id}
                    className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-raised)]/40"
                  >
                    <td className="px-4 py-3 whitespace-nowrap">{formatDate(r.performedDate)}</td>
                    <td className="px-4 py-3">{r.maintenanceType}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{r.description}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{r.technicianName}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {r.mileageAtService.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(r.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : workOrdersQ.isLoading ? (
        <Spinner label="Loading work orders…" />
      ) : workOrdersQ.isError ? (
        <ErrorBox>Couldn't load work orders.</ErrorBox>
      ) : (workOrdersQ.data ?? []).length === 0 ? (
        <Empty>No work orders on file.</Empty>
      ) : (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface-raised)]">
              <tr>
                <th className="text-left px-4 py-3">Number</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Priority</th>
                <th className="text-left px-4 py-3">Description</th>
                <th className="text-left px-4 py-3">Requested</th>
                <th className="text-right px-4 py-3">Cost</th>
              </tr>
            </thead>
            <tbody>
              {workOrdersQ.data!.map((wo) => (
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
                  <td className="px-4 py-3 whitespace-nowrap">{formatDate(wo.requestedDate)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {wo.totalCost !== null ? formatCurrency(wo.totalCost) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        '-mb-px px-4 py-2 text-sm font-medium border-b-2 transition-colors',
        active
          ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
          : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
      )}
    >
      {children}
    </button>
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

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">
      {children}
    </div>
  )
}

function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 text-[var(--color-danger)] px-3 py-2 text-sm">
      {children}
    </div>
  )
}

function NotFound() {
  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-2xl font-semibold">Vehicle not found</h1>
      <p className="text-sm text-[var(--color-text-muted)]">
        That vehicle ID doesn't exist in the seeded fleet.
      </p>
      <Link to="/vehicles" className="text-sm text-[var(--color-accent)] hover:underline">
        ← Back to vehicles
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
