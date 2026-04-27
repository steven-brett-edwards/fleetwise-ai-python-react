import { Link, useSearchParams } from 'react-router-dom'
import { useMemo } from 'react'
import { useVehicles } from '../hooks/useFleetData'
import Spinner from '../components/Spinner'
import StatusPill from '../components/StatusPill'

const STATUS_OPTIONS = ['', 'Active', 'InShop', 'OutOfService', 'Retired']
const FUEL_OPTIONS = ['', 'Gasoline', 'Diesel', 'Hybrid', 'CNG', 'Electric']
// Departments are discovered from the data itself so we don't drift.

export default function Vehicles() {
  const [params, setParams] = useSearchParams()
  const filters = {
    status: params.get('status') ?? undefined,
    department: params.get('department') ?? undefined,
    fuelType: params.get('fuelType') ?? undefined,
  }
  const { data, isLoading, isError } = useVehicles(filters)

  const departmentOptions = useMemo(() => {
    if (!data) return [''] as string[]
    return ['', ...Array.from(new Set(data.map((v) => v.department))).sort()]
  }, [data])

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold">Vehicles</h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          35 seeded public-works vehicles. Filter by status, department, or fuel type.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <Select
          label="Status"
          value={filters.status ?? ''}
          options={STATUS_OPTIONS}
          onChange={(v) => setFilter('status', v)}
        />
        <Select
          label="Department"
          value={filters.department ?? ''}
          options={departmentOptions}
          onChange={(v) => setFilter('department', v)}
        />
        <Select
          label="Fuel"
          value={filters.fuelType ?? ''}
          options={FUEL_OPTIONS}
          onChange={(v) => setFilter('fuelType', v)}
        />
      </div>

      {isLoading ? (
        <Spinner label="Loading vehicles…" />
      ) : isError ? (
        <div className="rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 text-[var(--color-danger)] px-3 py-2 text-sm">
          Couldn't load vehicles.
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface-raised)]">
              <tr>
                <th className="text-left px-4 py-3">Asset #</th>
                <th className="text-left px-4 py-3">Vehicle</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Department</th>
                <th className="text-left px-4 py-3">Fuel</th>
                <th className="text-right px-4 py-3">Mileage</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((v) => (
                <tr
                  key={v.id}
                  className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-raised)]/40"
                >
                  <td className="px-4 py-3 font-medium">
                    <Link
                      to={`/vehicles/${v.id}`}
                      className="text-[var(--color-accent)] hover:underline"
                    >
                      {v.assetNumber}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    {v.year} {v.make} {v.model}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill value={v.status} />
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{v.department}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{v.fuelType}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {v.currentMileage.toLocaleString()}
                  </td>
                </tr>
              ))}
              {data && data.length === 0 ? (
                <tr>
                  <td
                    className="px-4 py-8 text-center text-[var(--color-text-muted)]"
                    colSpan={6}
                  >
                    No vehicles match these filters.
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

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  onChange: (next: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-[var(--color-text)] normal-case px-3 py-2 focus:outline-none focus:border-[var(--color-accent)]"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt === '' ? 'All' : opt}
          </option>
        ))}
      </select>
    </label>
  )
}

