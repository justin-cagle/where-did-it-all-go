import { useState } from 'react'
import { NavLink } from 'react-router-dom'

const PRIMARY_ITEMS = [
  { to: '/dashboard', label: 'Overview', icon: DashboardIcon },
  { to: '/accounts', label: 'Accounts', icon: AccountsIcon },
  { to: '/transactions', label: 'Transactions', icon: TransactionsIcon },
  { to: '/budget', label: 'Budget', icon: BudgetIcon },
  { to: '/goals', label: 'Goals', icon: GoalsIcon },
]

const MORE_ITEMS = [
  { to: '/debts', label: 'Debts', icon: DebtsIcon },
  { to: '/calendar', label: 'Calendar', icon: CalendarIcon },
  { to: '/projections', label: 'Projections', icon: ProjectionsIcon },
  { to: '/insights', label: 'Insights', icon: InsightsIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function BottomNav() {
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <>
      {/* Backdrop for More sheet */}
      {moreOpen && (
        <div
          onClick={() => setMoreOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 40,
          }}
        />
      )}

      {/* More sheet */}
      {moreOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: 64,
            left: 0,
            right: 0,
            background: 'var(--bg-elevated)',
            borderTop: '1px solid var(--border)',
            borderRadius: '16px 16px 0 0',
            padding: '16px 12px',
            zIndex: 50,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {MORE_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMoreOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                borderRadius: 10,
                background: isActive
                  ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                  : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--fg-primary)',
                textDecoration: 'none',
                fontSize: 15,
                fontWeight: isActive ? 500 : 400,
              })}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      )}

      {/* Tab bar */}
      <nav
        aria-label="Mobile navigation"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 64,
          background: 'var(--bg-elevated)',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'stretch',
          zIndex: 30,
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        {PRIMARY_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 3,
              textDecoration: 'none',
              color: isActive ? 'var(--accent)' : 'var(--fg-muted)',
              fontSize: 10,
              fontWeight: isActive ? 500 : 400,
            })}
          >
            <Icon />
            <span>{label}</span>
          </NavLink>
        ))}

        {/* More button */}
        <button
          onClick={() => setMoreOpen((v) => !v)}
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 3,
            background: 'transparent',
            border: 'none',
            color: moreOpen ? 'var(--accent)' : 'var(--fg-muted)',
            fontSize: 10,
            fontWeight: moreOpen ? 500 : 400,
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
          aria-expanded={moreOpen}
          aria-haspopup="menu"
        >
          <MoreIcon />
          <span>More</span>
        </button>
      </nav>
    </>
  )
}

function DashboardIcon() {
  return (
    <svg
      width="20"
      height="20"
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
      width="20"
      height="20"
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
      width="20"
      height="20"
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
      width="20"
      height="20"
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
      width="20"
      height="20"
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
      width="20"
      height="20"
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
      width="20"
      height="20"
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
function ProjectionsIcon() {
  return (
    <svg
      width="20"
      height="20"
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
      width="20"
      height="20"
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
function SettingsIcon() {
  return (
    <svg
      width="20"
      height="20"
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
function MoreIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
      <circle cx="5" cy="12" r="1" />
    </svg>
  )
}
