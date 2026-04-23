import { AlertTriangle, CheckCircle2, Truck, Wrench } from 'lucide-react'
import StatCard from '../components/StatCard'
import Spinner from '../components/Spinner'
import {
  useFleetSummary,
  useOverdueMaintenance,
  useUpcomingMaintenance,
} from '../hooks/useFleetData'

export default function Dashboard() {
  const summary = useFleetSummary()
  const overdue = useOverdueMaintenance()
  const upcoming = useUpcomingMaintenance()

  return (
    <div className="space-y-8 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold">Fleet Dashboard</h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Snapshot of the public-works fleet — live from the FastAPI backend.
        </p>
      </header>

      {summary.isLoading ? (
        <Spinner label="Loading fleet summary…" />
      ) : summary.isError ? (
        <ErrorBanner message="Couldn't load fleet summary." />
      ) : summary.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total vehicles" value={summary.data.totalVehicles} icon={Truck} />
          <StatCard
            label="Active"
            value={summary.data.byStatus.Active ?? 0}
            icon={CheckCircle2}
            tone="success"
          />
          <StatCard
            label="In shop"
            value={summary.data.byStatus.InShop ?? 0}
            icon={Wrench}
            tone="accent"
          />
          <StatCard
            label="Out of service"
            value={summary.data.byStatus.OutOfService ?? 0}
            icon={AlertTriangle}
            tone="danger"
          />
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <MaintenancePanel
          title="Overdue maintenance"
          accent="danger"
          loading={overdue.isLoading}
          error={overdue.isError}
          items={overdue.data?.slice(0, 5) ?? []}
          emptyMessage="Nothing overdue. Good fleet."
        />
        <MaintenancePanel
          title="Upcoming (next 30 days / 5,000 mi)"
          accent="accent"
          loading={upcoming.isLoading}
          error={upcoming.isError}
          items={upcoming.data?.slice(0, 10) ?? []}
          emptyMessage="No upcoming items in window."
        />
      </div>
    </div>
  )
}

interface PanelProps {
  title: string
  accent: 'danger' | 'accent'
  loading: boolean
  error: boolean
  items: Array<{
    id: number
    vehicleAssetNumber: string
    vehicleDescription: string
    maintenanceType: string
    nextDueDate: string | null
    nextDueMileage: number | null
  }>
  emptyMessage: string
}

function MaintenancePanel({ title, accent, loading, error, items, emptyMessage }: PanelProps) {
  return (
    <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
        <span
          className={
            accent === 'danger' ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'
          }
        >
          ●
        </span>{' '}
        {title}
      </h2>
      <div className="mt-3">
        {loading ? (
          <Spinner />
        ) : error ? (
          <ErrorBanner message="Couldn't load maintenance data." />
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{emptyMessage}</p>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {items.map((item) => (
              <li key={item.id} className="py-3 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-medium truncate">
                    <span className="text-[var(--color-accent)]">#{item.vehicleAssetNumber}</span>{' '}
                    <span className="text-[var(--color-text-muted)]">
                      · {item.vehicleDescription}
                    </span>
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {item.maintenanceType}
                  </div>
                </div>
                <div className="text-right text-xs text-[var(--color-text-muted)] whitespace-nowrap">
                  {item.nextDueDate ? formatDate(item.nextDueDate) : '—'}
                  {item.nextDueMileage ? (
                    <div>@ {item.nextDueMileage.toLocaleString()} mi</div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 text-[var(--color-danger)] px-3 py-2 text-sm">
      {message}
    </div>
  )
}
