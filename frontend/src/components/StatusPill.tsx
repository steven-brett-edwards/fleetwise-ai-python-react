import clsx from 'clsx'

const VEHICLE_TONES: Record<string, string> = {
  Active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  InShop: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  OutOfService: 'bg-red-500/10 text-red-400 border-red-500/30',
  Retired: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
}

const WORK_ORDER_TONES: Record<string, string> = {
  Open: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  InProgress: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  Completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  Cancelled: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
}

const PRIORITY_TONES: Record<string, string> = {
  Low: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
  Medium: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  High: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  Critical: 'bg-red-500/10 text-red-400 border-red-500/30',
}

const FALLBACK = 'bg-gray-500/10 text-gray-400 border-gray-500/30'

export type PillKind = 'vehicle' | 'workOrder' | 'priority'

const TONES: Record<PillKind, Record<string, string>> = {
  vehicle: VEHICLE_TONES,
  workOrder: WORK_ORDER_TONES,
  priority: PRIORITY_TONES,
}

export default function StatusPill({ value, kind = 'vehicle' }: { value: string; kind?: PillKind }) {
  const tone = TONES[kind][value] ?? FALLBACK
  return (
    <span
      className={clsx(
        'inline-block rounded-full border px-2 py-0.5 text-xs font-medium',
        tone,
      )}
    >
      {value}
    </span>
  )
}
