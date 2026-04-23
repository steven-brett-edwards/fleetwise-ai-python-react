import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Truck,
  MessageSquare,
  Wrench,
  ClipboardList,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'

function Item({ to, icon: Icon, label }: { to: string; icon: LucideIcon; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-[var(--color-surface-raised)] text-[var(--color-accent)]'
            : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-raised)]/60',
        )
      }
    >
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </NavLink>
  )
}

function Disabled({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm text-gray-600 cursor-not-allowed">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4" />
        <span>{label}</span>
      </div>
      <span className="text-[10px] uppercase tracking-wider rounded bg-gray-800 text-gray-400 px-1.5 py-0.5">
        soon
      </span>
    </div>
  )
}

export default function Sidenav() {
  return (
    <aside className="sticky top-0 h-screen w-56 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-6 flex flex-col gap-6">
      <div className="flex items-center gap-2 px-2">
        <Zap className="h-6 w-6 text-[var(--color-accent)]" />
        <div>
          <div className="text-base font-semibold leading-tight">FleetWise</div>
          <div className="text-xs text-[var(--color-text-muted)] leading-tight">AI</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1">
        <Item to="/" icon={LayoutDashboard} label="Dashboard" />
        <Item to="/vehicles" icon={Truck} label="Vehicles" />
        <Item to="/chat" icon={MessageSquare} label="Chat" />
        <Disabled icon={Wrench} label="Vehicle detail" />
        <Disabled icon={ClipboardList} label="Work orders" />
      </nav>
      <div className="mt-auto text-[11px] leading-relaxed text-[var(--color-text-muted)] px-2">
        <p>
          Python edition.{' '}
          <a
            href="https://github.com/steven-brett-edwards/fleetwise-ai-python-react"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-[var(--color-accent)]"
          >
            Source
          </a>
          .
        </p>
      </div>
    </aside>
  )
}
