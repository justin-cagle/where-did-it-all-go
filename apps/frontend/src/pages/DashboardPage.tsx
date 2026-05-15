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
  return <PlaceholderPage title="Settings" />
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
