export function DashboardPage() {
  return <PlaceholderPage title="Overview" />
}

export { AccountsPage } from './accounts/AccountsPage'
export { TransactionsPage } from './transactions/TransactionsPage'

export function BudgetPage() {
  return <PlaceholderPage title="Budget" />
}

export function GoalsPage() {
  return <PlaceholderPage title="Goals" />
}

export function DebtsPage() {
  return <PlaceholderPage title="Debts" />
}

export function CalendarPage() {
  return <PlaceholderPage title="Calendar" />
}

export function SettingsPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h1
        style={{
          fontSize: 22,
          fontWeight: 600,
          color: 'var(--fg-primary)',
          margin: 0,
          letterSpacing: '-0.01em',
        }}
      >
        Settings
      </h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
        <a
          href="/settings/classification"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            padding: '14px 16px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            textDecoration: 'none',
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Classification
          </span>
          <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Categories, tags, rules, and income sources
          </span>
        </a>
      </div>
    </div>
  )
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h1
        style={{
          fontSize: 22,
          fontWeight: 600,
          color: 'var(--fg-primary)',
          margin: 0,
          letterSpacing: '-0.01em',
        }}
      >
        {title}
      </h1>
      <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
        This section is coming soon.
      </p>
    </div>
  )
}
