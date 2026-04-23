import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import clsx from 'clsx'

interface StatCardProps {
  label: string
  value: ReactNode
  icon?: LucideIcon
  tone?: 'default' | 'accent' | 'danger' | 'success'
}

const toneStyles: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'text-[var(--color-text)]',
  accent: 'text-[var(--color-accent)]',
  danger: 'text-[var(--color-danger)]',
  success: 'text-[var(--color-success)]',
}

export default function StatCard({ label, value, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
          {label}
        </span>
        {Icon ? <Icon className={clsx('h-4 w-4', toneStyles[tone])} /> : null}
      </div>
      <div className={clsx('mt-3 text-3xl font-semibold', toneStyles[tone])}>{value}</div>
    </div>
  )
}
