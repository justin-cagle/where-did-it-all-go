import { NavLink } from 'react-router-dom'

interface SidebarProps {
  compact: boolean
  onToggleCompact: () => void
}

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Overview', icon: DashboardIcon },
  { to: '/accounts', label: 'Accounts', icon: AccountsIcon },
  { to: '/transactions', label: 'Transactions', icon: TransactionsIcon },
  { to: '/budget', label: 'Budget', icon: BudgetIcon },
  { to: '/goals', label: 'Goals', icon: GoalsIcon },
  { to: '/debts', label: 'Debts', icon: DebtsIcon },
  { to: '/calendar', label: 'Calendar', icon: CalendarIcon },
  { to: '/projections', label: 'Projections', icon: ProjectionsIcon },
  { to: '/insights', label: 'Insights', icon: InsightsIcon },
]

export function Sidebar({ compact, onToggleCompact }: SidebarProps) {
  const w = compact ? 52 : 200

  return (
    <nav
      aria-label="Primary navigation"
      style={{
        width: w,
        minWidth: w,
        height: '100%',
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        padding: compact ? '12px 8px' : '16px 12px',
        gap: 2,
        flexShrink: 0,
        transition: 'width 0.2s',
        overflow: 'hidden',
      }}
    >
      {/* Logo + wordmark */}
      <div
        style={{
          padding: compact ? '6px 6px 14px' : '6px 8px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            flexShrink: 0,
            background: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span
            style={{
              color: 'var(--accent-fg)',
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            $
          </span>
        </div>
        {!compact && (
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 15,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              whiteSpace: 'nowrap',
            }}
          >
            wdiag
          </span>
        )}
      </div>

      {/* Nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 6,
              background: isActive
                ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--fg-secondary)',
              textDecoration: 'none',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              transition: 'background 0.1s, color 0.1s',
              whiteSpace: 'nowrap',
            })}
          >
            <Icon />
            {!compact && <span>{label}</span>}
          </NavLink>
        ))}
      </div>

      {/* Bottom: settings + compact toggle */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flexShrink: 0 }}>
        <NavLink
          to="/settings"
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '8px 10px',
            borderRadius: 6,
            background: isActive
              ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
              : 'transparent',
            color: isActive ? 'var(--accent)' : 'var(--fg-muted)',
            textDecoration: 'none',
            fontSize: 13,
            transition: 'background 0.1s, color 0.1s',
            whiteSpace: 'nowrap',
          })}
        >
          <SettingsIcon />
          {!compact && <span>Settings</span>}
        </NavLink>

        <button
          onClick={onToggleCompact}
          aria-label={compact ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: compact ? 'center' : 'flex-start',
            gap: 10,
            padding: '8px 10px',
            borderRadius: 6,
            background: 'transparent',
            border: 'none',
            color: 'var(--fg-muted)',
            fontSize: 13,
            cursor: 'pointer',
            transition: 'color 0.1s',
            width: '100%',
            whiteSpace: 'nowrap',
          }}
        >
          <CollapseIcon flipped={compact} />
          {!compact && <span>Collapse</span>}
        </button>
      </div>
    </nav>
  )
}

/* ── Nav icons — paths copied from dashboard.html icons object ── */

function DashboardIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  )
}

function AccountsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <line x1="2" y1="10" x2="22" y2="10" />
    </svg>
  )
}

function TransactionsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  )
}

function BudgetIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  )
}

function GoalsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  )
}

function DebtsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  )
}

function SettingsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

function ProjectionsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}

function InsightsIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2a7 7 0 0 1 7 7c0 3.87-3 7-7 9-4-2-7-5.13-7-9a7 7 0 0 1 7-7z" />
      <path d="M12 18v4M8 22h8" />
    </svg>
  )
}

function CollapseIcon({ flipped }: { flipped: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      style={{ transform: flipped ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
    >
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}
