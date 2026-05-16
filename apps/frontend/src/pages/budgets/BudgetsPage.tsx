import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useListBudgetsApiV1HouseholdsHouseholdIdBudgetsGet } from '@/api/generated/budgets/budgets'
import { useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet } from '@/api/generated/budgets/budgets'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import type { BudgetOut } from '@/api/generated/model/budgetOut'
import { BudgetSetupWizard } from './BudgetSetupWizard'

function progressColor(pct: number): string {
  if (pct >= 100) return 'var(--danger)'
  if (pct >= 80) return 'var(--warning)'
  return 'var(--success)'
}

function daysRemaining(periodEnd: string): number {
  const end = new Date(periodEnd)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.max(0, Math.ceil((end.getTime() - today.getTime()) / 86400000))
}

function periodLabel(period: string): string {
  const map: Record<string, string> = {
    monthly: 'Monthly',
    weekly: 'Weekly',
    biweekly: 'Biweekly',
    semimonthly: 'Semimonthly',
    annual: 'Annual',
    custom: 'Custom',
  }
  return map[period] ?? period
}

function methodLabel(method: string): string {
  const map: Record<string, string> = {
    zero_based: 'Zero-Based',
    envelope: 'Envelope',
    fifty_thirty_twenty: '50/30/20',
    percentage_based: 'Percentage',
    rolling_average: 'Rolling Avg',
    manual: 'Manual',
    none: 'Tracking',
  }
  return map[method] ?? method
}

function Badge({ label, color = 'var(--fg-muted)' }: { label: string; color?: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 500,
        background: `color-mix(in oklch, ${color} 15%, transparent)`,
        color,
        border: `1px solid color-mix(in oklch, ${color} 30%, transparent)`,
      }}
    >
      {label}
    </span>
  )
}

function BudgetCard({
  budget,
  householdId,
  onClick,
}: {
  budget: BudgetOut
  householdId: string
  onClick: () => void
}) {
  const { data: status } = useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet(
    householdId,
    budget.id,
    {},
    { query: { enabled: !!householdId } }
  )

  const expectedIncome = budget.expected_income ? parseFloat(budget.expected_income) : null
  const totalSpent = status ? status.lines.reduce((s, l) => s + parseFloat(l.actual), 0) : null
  const statusExpectedIncome =
    status?.expected_income != null ? parseFloat(status.expected_income) : expectedIncome

  const overallPct =
    totalSpent != null && statusExpectedIncome && statusExpectedIncome > 0
      ? Math.min(100, Math.round((totalSpent / statusExpectedIncome) * 100))
      : null

  const days = status ? daysRemaining(status.period_end) : null

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '18px 20px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        transition: 'box-shadow 0.15s, border-color 0.15s',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'var(--border-strong)'
        el.style.boxShadow = 'var(--shadow)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'var(--border)'
        el.style.boxShadow = 'none'
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
          {budget.name}
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <Badge label={periodLabel(budget.period)} color="var(--accent)" />
          <Badge label={methodLabel(budget.method)} />
        </div>
      </div>

      {totalSpent != null && statusExpectedIncome != null ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <span
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  fontFamily: "'Geist Mono', monospace",
                  color: 'var(--fg-primary)',
                  letterSpacing: '-0.02em',
                }}
              >
                {formatAmount(totalSpent, { currency: budget.currency })}
              </span>
              <span style={{ fontSize: 13, color: 'var(--fg-muted)', marginLeft: 6 }}>
                of {formatAmount(statusExpectedIncome, { currency: budget.currency })}
              </span>
            </div>
            {overallPct != null && (
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: progressColor(overallPct),
                  fontFamily: "'Geist Mono', monospace",
                }}
              >
                {overallPct}%
              </span>
            )}
          </div>

          {overallPct != null && (
            <div
              style={{
                height: 6,
                borderRadius: 99,
                background: 'var(--border)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${Math.min(100, overallPct)}%`,
                  borderRadius: 99,
                  background: progressColor(overallPct),
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          )}

          {days != null && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              {days === 0 ? 'Period ends today' : `${days} days remaining`}
            </div>
          )}
        </div>
      ) : (
        <div style={{ height: 62, background: 'var(--bg-secondary)', borderRadius: 8 }} />
      )}
    </div>
  )
}

export function BudgetsPage() {
  const { householdId } = useHousehold()
  const navigate = useNavigate()
  const [showWizard, setShowWizard] = useState(false)

  const hid = householdId ?? ''

  const { data: budgets = [], isLoading } = useListBudgetsApiV1HouseholdsHouseholdIdBudgetsGet(
    hid,
    { query: { enabled: !!hid } }
  )

  if (!householdId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: 0,
            letterSpacing: '-0.01em',
          }}
        >
          Budgets
        </h1>
        <button
          type="button"
          onClick={() => setShowWizard(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 14px',
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          <Plus size={14} />
          Add budget
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {isLoading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
        ) : budgets.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              padding: '80px 24px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              No budgets yet
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
              Create your first budget to start tracking
            </div>
            <button
              type="button"
              onClick={() => setShowWizard(true)}
              style={{
                marginTop: 8,
                padding: '8px 18px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Create budget
            </button>
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: 12,
            }}
          >
            {budgets.map((b) => (
              <BudgetCard
                key={b.id}
                budget={b}
                householdId={hid}
                onClick={() => navigate(`/budget/${b.id}`)}
              />
            ))}
          </div>
        )}
      </div>

      {showWizard && (
        <BudgetSetupWizard
          householdId={hid}
          onClose={() => setShowWizard(false)}
          onCreated={(id) => {
            setShowWizard(false)
            navigate(`/budget/${id}`)
          }}
        />
      )}
    </div>
  )
}
