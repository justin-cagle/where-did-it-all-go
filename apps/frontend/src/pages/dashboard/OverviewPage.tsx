import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import {
  useListBudgetsApiV1HouseholdsHouseholdIdBudgetsGet,
  useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet,
} from '@/api/generated/budgets/budgets'
import { useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet } from '@/api/generated/transactions/transactions'
import { useGetExpectedEventsApiV1HouseholdsHouseholdIdRecurrencesExpectedGet } from '@/api/generated/recurrences/recurrences'
import {
  useListGoalsApiV1HouseholdsHouseholdIdGoalsGet,
  useAllGoalsStatusApiV1HouseholdsHouseholdIdGoalsStatusGet,
} from '@/api/generated/default/default'
import { useHousehold } from '@/hooks/use-household'
import { useAuthStore } from '@/store'
import { formatAmount } from '@/lib/format-amount'
import type { PrivacyMode } from '@/lib/format-amount'
import { calcNetWorth, isLiabilityType } from '@/domain/accounts'
import { GoalStatus } from '@/api/generated/model/goalStatus'
import { BurnUpStatus } from '@/api/generated/model/burnUpStatus'
import type { BudgetOut } from '@/api/generated/model/budgetOut'
import type { GoalOut } from '@/api/generated/model/goalOut'
import type { GoalSnapshotOut } from '@/api/generated/model/goalSnapshotOut'
import type { ExpectedEventOut } from '@/api/generated/model/expectedEventOut'
import type { TransactionOut } from '@/api/generated/model/transactionOut'

function fmtDate(dateStr: string): string {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function daysFromToday(dateStr: string): number {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  const target = new Date(y, m - 1, d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.ceil((target.getTime() - today.getTime()) / 86400000)
}

function upcomingDateRange(): { from: string; to: string } {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const toDateStr = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const to = new Date(now)
  to.setDate(to.getDate() + 14)
  return { from: toDateStr(now), to: toDateStr(to) }
}

function burnUpColor(status: string): string {
  if (status === BurnUpStatus.ahead || status === BurnUpStatus.on_track) return 'var(--success)'
  if (status === BurnUpStatus.behind || status === BurnUpStatus.at_risk) return 'var(--warning)'
  return 'var(--danger)'
}

function spendColor(pct: number): string {
  if (pct >= 100) return 'var(--danger)'
  if (pct >= 80) return 'var(--warning)'
  return 'var(--success)'
}

const CARD: React.CSSProperties = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
}

function CardHeader({
  title,
  linkTo,
  navigate,
}: {
  title: string
  linkTo: string
  navigate: ReturnType<typeof useNavigate>
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 16px',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>{title}</span>
      <button
        type="button"
        onClick={() => navigate(linkTo)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 3,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 12,
          color: 'var(--fg-muted)',
          padding: 0,
        }}
      >
        View all
        <ArrowRight size={12} />
      </button>
    </div>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div
      style={{ padding: '24px 16px', textAlign: 'center', fontSize: 13, color: 'var(--fg-muted)' }}
    >
      {msg}
    </div>
  )
}

function BudgetWidget({ budget, householdId }: { budget: BudgetOut; householdId: string }) {
  const { data: status } = useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet(
    householdId,
    budget.id,
    undefined,
    { query: { staleTime: 60_000 } }
  )

  const totalPlanned = status?.lines.reduce((acc, l) => acc + parseFloat(l.planned), 0) ?? 0
  const totalActual = status?.lines.reduce((acc, l) => acc + parseFloat(l.actual), 0) ?? 0
  const pct = totalPlanned > 0 ? (totalActual / totalPlanned) * 100 : 0
  const color = spendColor(pct)
  const daysLeft = status ? daysFromToday(status.period_end) : null

  return (
    <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>
        {budget.name}
      </div>
      {status ? (
        <>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              color: 'var(--fg-muted)',
            }}
          >
            <span>
              {formatAmount(totalActual, { currency: budget.currency })} of{' '}
              {formatAmount(totalPlanned, { currency: budget.currency })}
            </span>
            <span
              style={{
                fontWeight: 600,
                color,
                fontFamily: "'Geist Mono', monospace",
              }}
            >
              {Math.round(pct)}%
            </span>
          </div>
          <div
            style={{ height: 6, borderRadius: 99, background: 'var(--border)', overflow: 'hidden' }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, pct)}%`,
                borderRadius: 99,
                background: color,
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          {daysLeft != null && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              {daysLeft === 0
                ? 'Period ends today'
                : daysLeft < 0
                  ? `Period ended ${Math.abs(daysLeft)}d ago`
                  : `${daysLeft} days remaining`}
            </div>
          )}
        </>
      ) : (
        <div style={{ height: 6, borderRadius: 99, background: 'var(--border)' }} />
      )}
    </div>
  )
}

function GoalRow({ goal, snapshot }: { goal: GoalOut; snapshot: GoalSnapshotOut | undefined }) {
  const pct = snapshot ? Math.min(100, Math.round(parseFloat(snapshot.progress_pct))) : null
  const color = snapshot ? burnUpColor(snapshot.burn_up_status) : 'var(--accent)'

  return (
    <div
      style={{
        padding: '10px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--fg-primary)',
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {goal.name}
        </span>
        {pct != null && (
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color,
              fontFamily: "'Geist Mono', monospace",
              flexShrink: 0,
              marginLeft: 8,
            }}
          >
            {pct}%
          </span>
        )}
      </div>
      <div style={{ height: 4, borderRadius: 99, background: 'var(--border)', overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct ?? 0}%`,
            borderRadius: 99,
            background: color,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  )
}

function TxRow({ tx, privacyMode }: { tx: TransactionOut; privacyMode: PrivacyMode }) {
  const isDebit = tx.direction === 'debit'
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        gap: 8,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--fg-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {tx.merchant_name ?? tx.description}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
          {fmtDate(tx.posted_date)}
        </div>
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: isDebit ? 'var(--fg-primary)' : 'var(--success)',
          flexShrink: 0,
          fontFamily: "'Geist Mono', monospace",
        }}
      >
        {isDebit ? '-' : '+'}
        {formatAmount(parseFloat(tx.amount), { currency: tx.currency, privacyMode })}
      </div>
    </div>
  )
}

function RecurrenceRow({ event }: { event: ExpectedEventOut }) {
  const days = daysFromToday(event.expected_date)
  const daysLabel = days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : `In ${days} days`
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        gap: 8,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--fg-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {event.merchant_name ?? 'Recurring'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
          {daysLabel} &middot; {fmtDate(event.expected_date)}
        </div>
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--fg-secondary)',
          flexShrink: 0,
          fontFamily: "'Geist Mono', monospace",
        }}
      >
        {formatAmount(Math.abs(parseFloat(event.expected_amount)), { currency: event.currency })}
      </div>
    </div>
  )
}

export function OverviewPage() {
  const { householdId } = useHousehold()
  const navigate = useNavigate()
  const privacyMode = useAuthStore((s) => s.privacyMode)

  const hid = householdId ?? ''
  const enabled = !!householdId

  const { data: accounts = [] } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    hid,
    undefined,
    { query: { enabled, staleTime: 60_000 } }
  )

  const { data: budgets = [] } = useListBudgetsApiV1HouseholdsHouseholdIdBudgetsGet(hid, {
    query: { enabled, staleTime: 60_000 },
  })

  const { data: allTxns = [] } =
    useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet(hid, undefined, {
      query: { enabled, staleTime: 0 },
    })

  const { from, to } = upcomingDateRange()
  const { data: expectedEvents = [] } =
    useGetExpectedEventsApiV1HouseholdsHouseholdIdRecurrencesExpectedGet(
      hid,
      { from, to },
      { query: { enabled, staleTime: 60_000 } }
    )

  const { data: goals = [] } = useListGoalsApiV1HouseholdsHouseholdIdGoalsGet(
    hid,
    { status: GoalStatus.active },
    { query: { enabled, staleTime: 60_000 } }
  )

  const { data: goalSnapshots = [] } = useAllGoalsStatusApiV1HouseholdsHouseholdIdGoalsStatusGet(
    hid,
    { query: { enabled, staleTime: 60_000 } }
  )

  const netWorth = calcNetWorth(accounts)
  const totalAssets = accounts
    .filter((a) => !isLiabilityType(a.account_type))
    .reduce((sum, a) => sum + parseFloat(a.current_balance), 0)
  const totalLiabilities = accounts
    .filter((a) => isLiabilityType(a.account_type))
    .reduce((sum, a) => sum + parseFloat(a.current_balance), 0)

  const snapshotByGoalId = new Map<string, GoalSnapshotOut>(
    goalSnapshots.map((s) => [s.goal_id, s])
  )

  const activeBudget = budgets[0] ?? null
  const topGoals = goals.slice(0, 3)
  const recentTxns = allTxns.slice(0, 5)
  const sortedEvents = [...expectedEvents]
    .sort((a, b) => a.expected_date.localeCompare(b.expected_date))
    .slice(0, 6)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border)',
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
          Overview
        </h1>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {/* Net Worth */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => navigate('/accounts')}
          onKeyDown={(e) => e.key === 'Enter' && navigate('/accounts')}
          onMouseEnter={(e) => {
            ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'
          }}
          onMouseLeave={(e) => {
            ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'
          }}
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '20px 24px',
            cursor: 'pointer',
            transition: 'border-color 0.15s',
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--fg-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 8,
            }}
          >
            Net Worth
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: netWorth >= 0 ? 'var(--fg-primary)' : 'var(--danger)',
              letterSpacing: '-0.02em',
              marginBottom: 14,
            }}
          >
            {formatAmount(netWorth, { privacyMode })}
          </div>
          <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 2 }}>Assets</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--success)' }}>
                {formatAmount(totalAssets, { privacyMode })}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 2 }}>
                Liabilities
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--danger)' }}>
                {formatAmount(totalLiabilities, { privacyMode })}
              </div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <ArrowRight size={16} style={{ color: 'var(--fg-muted)' }} />
            </div>
          </div>
        </div>

        {/* Card grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: 16,
          }}
        >
          {/* Budget */}
          <div style={CARD}>
            <CardHeader title="Budget" linkTo="/budget" navigate={navigate} />
            {activeBudget ? (
              <BudgetWidget budget={activeBudget} householdId={hid} />
            ) : (
              <EmptyState msg="No budgets yet" />
            )}
          </div>

          {/* Goals */}
          <div style={CARD}>
            <CardHeader title="Goals" linkTo="/goals" navigate={navigate} />
            {topGoals.length === 0 ? (
              <EmptyState msg="No active goals" />
            ) : (
              <div>
                {topGoals.map((g) => (
                  <GoalRow key={g.id} goal={g} snapshot={snapshotByGoalId.get(g.id)} />
                ))}
              </div>
            )}
          </div>

          {/* Recent Transactions */}
          <div style={CARD}>
            <CardHeader title="Recent Transactions" linkTo="/transactions" navigate={navigate} />
            {recentTxns.length === 0 ? (
              <EmptyState msg="No transactions yet" />
            ) : (
              <div>
                {recentTxns.map((tx) => (
                  <TxRow key={tx.id} tx={tx} privacyMode={privacyMode} />
                ))}
              </div>
            )}
          </div>

          {/* Upcoming Recurrences */}
          <div style={CARD}>
            <CardHeader title="Upcoming (14 days)" linkTo="/calendar" navigate={navigate} />
            {sortedEvents.length === 0 ? (
              <EmptyState msg="No upcoming recurrences" />
            ) : (
              <div>
                {sortedEvents.map((ev) => (
                  <RecurrenceRow key={`${ev.recurrence_id}-${ev.expected_date}`} event={ev} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
