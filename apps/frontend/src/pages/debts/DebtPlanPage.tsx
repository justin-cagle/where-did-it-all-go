import { useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronDown, CalendarCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetPlanApiV1HouseholdsHouseholdIdDebtPlansPlanIdGet,
  useGetSummaryApiV1HouseholdsHouseholdIdDebtPlansPlanIdSummaryGet,
  useGetScheduleApiV1HouseholdsHouseholdIdDebtPlansPlanIdScheduleGet,
  useComparePlansApiV1HouseholdsHouseholdIdDebtPlansPlanIdComparisonGet,
  useRecordPaymentApiV1HouseholdsHouseholdIdDebtPlansAccountsAccountIdPaymentPost,
} from '@/api/generated/default/default'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { isLiabilityType } from '@/domain/accounts'
import type { DebtPlanScheduleByAccount } from '@/api/generated/model/debtPlanScheduleByAccount'
import type { DebtPlanScheduleRow } from '@/api/generated/model/debtPlanScheduleRow'

const VIRTUALIZE_THRESHOLD = 60
const ROW_HEIGHT = 40
const INITIAL_SHOW = 12

function methodLabel(method: string): string {
  const map: Record<string, string> = {
    avalanche: 'Avalanche',
    snowball: 'Snowball',
    custom: 'Custom',
    none: 'Track only',
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

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Unknown'
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
  })
}

function SummaryPanel({
  summary,
  currency,
}: {
  summary: {
    total_interest: string
    total_paid: string
    months_to_payoff: number
    interest_savings_vs_minimums: string
    payoff_date: string | null
  }
  currency: string
}) {
  const items = [
    {
      label: 'Total interest',
      value: formatAmount(summary.total_interest, { currency }),
      color: 'var(--danger)',
    },
    {
      label: 'Total paid',
      value: formatAmount(summary.total_paid, { currency }),
      color: 'var(--fg-primary)',
    },
    {
      label: 'Months to payoff',
      value: String(summary.months_to_payoff),
      color: 'var(--fg-primary)',
    },
    {
      label: 'Payoff date',
      value: formatDate(summary.payoff_date),
      color: 'var(--fg-primary)',
    },
    {
      label: 'Interest savings',
      value: formatAmount(summary.interest_savings_vs_minimums, { currency }),
      subtitle: 'vs paying minimums only',
      color: 'var(--success)',
    },
  ]

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: 12,
        padding: '16px 18px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
      }}
    >
      {items.map((item) => (
        <div key={item.label}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 4,
            }}
          >
            {item.label}
          </div>
          <div
            style={{
              fontSize: 17,
              fontWeight: 700,
              fontFamily: "'Geist Mono', monospace",
              color: item.color,
              letterSpacing: '-0.01em',
            }}
          >
            {item.value}
          </div>
          {item.subtitle && (
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
              {item.subtitle}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

const COMPARE_TABS = [
  { id: 'minimums', label: 'Minimums Only' },
  { id: 'avalanche', label: 'Avalanche' },
  { id: 'snowball', label: 'Snowball' },
] as const

function ComparisonPanel({
  householdId,
  planId,
  planCurrency,
}: {
  householdId: string
  planId: string
  planCurrency: string
}) {
  const [compareMethod, setCompareMethod] = useState<string>('minimums')

  const { data: comparison } =
    useComparePlansApiV1HouseholdsHouseholdIdDebtPlansPlanIdComparisonGet(
      householdId,
      planId,
      { compare: compareMethod },
      { query: { enabled: !!householdId && !!planId } }
    )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--border)' }}>
        {COMPARE_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setCompareMethod(tab.id)}
            style={{
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: compareMethod === tab.id ? 600 : 400,
              color: compareMethod === tab.id ? 'var(--accent)' : 'var(--fg-secondary)',
              background: 'none',
              border: 'none',
              borderBottom:
                compareMethod === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
              cursor: 'pointer',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {comparison ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 12,
          }}
        >
          {[
            { label: 'Current Plan', data: comparison.current },
            {
              label: COMPARE_TABS.find((t) => t.id === compareMethod)?.label ?? compareMethod,
              data: comparison.compared,
            },
          ].map(({ label, data }) => (
            <div
              key={label}
              style={{
                padding: '14px 16px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 10,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--fg-secondary)',
                  marginBottom: 10,
                }}
              >
                {label}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Total interest</div>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      fontFamily: "'Geist Mono', monospace",
                      color: 'var(--danger)',
                    }}
                  >
                    {formatAmount(data.total_interest, { currency: planCurrency })}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Payoff date</div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                    {formatDate(data.payoff_date)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Months</div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: 'var(--fg-primary)',
                      fontFamily: "'Geist Mono', monospace",
                    }}
                  >
                    {data.months_to_payoff}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading comparison...</div>
      )}
    </div>
  )
}

function VirtualizedScheduleTable({
  rows,
  currency,
}: {
  rows: DebtPlanScheduleRow[]
  currency: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)

  const totalHeight = rows.length * ROW_HEIGHT
  const containerHeight = 400

  const startIdx = Math.floor(scrollTop / ROW_HEIGHT)
  const endIdx = Math.min(rows.length - 1, startIdx + Math.ceil(containerHeight / ROW_HEIGHT) + 2)

  const visibleRows = rows.slice(startIdx, endIdx + 1)

  const cols = ['Period', 'Opening', 'Payment', 'Principal', 'Interest', 'Closing']
  const colWidth = [100, 110, 100, 100, 100, 110]

  function cellStyle(i: number) {
    return {
      width: colWidth[i],
      flexShrink: 0,
      textAlign: (i === 0 ? 'left' : 'right') as 'left' | 'right',
      fontSize: 12,
      fontFamily: i > 0 ? "'Geist Mono', monospace" : undefined,
      paddingRight: 8,
    }
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          padding: '8px 12px',
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {cols.map((col, i) => (
          <div key={col} style={{ ...cellStyle(i), color: 'var(--fg-muted)', fontWeight: 500 }}>
            {col}
          </div>
        ))}
      </div>

      {/* Virtualized rows */}
      <div
        ref={containerRef}
        style={{ height: containerHeight, overflowY: 'auto', position: 'relative' }}
        onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
      >
        <div style={{ height: totalHeight, position: 'relative' }}>
          <div
            style={{
              position: 'absolute',
              top: startIdx * ROW_HEIGHT,
              width: '100%',
            }}
          >
            {visibleRows.map((row, i) => {
              const absoluteIdx = startIdx + i
              return (
                <div
                  key={row.id}
                  style={{
                    display: 'flex',
                    padding: '0 12px',
                    height: ROW_HEIGHT,
                    alignItems: 'center',
                    background: row.is_payoff
                      ? 'color-mix(in oklch, var(--success) 10%, transparent)'
                      : absoluteIdx % 2 === 0
                        ? 'transparent'
                        : 'color-mix(in oklch, var(--fg-primary) 2%, transparent)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div
                    style={{
                      ...cellStyle(0),
                      color: row.is_payoff ? 'var(--success)' : 'var(--fg-secondary)',
                    }}
                  >
                    {formatDate(row.period_date)}
                    {row.is_payoff ? ' ✓' : ''}
                  </div>
                  {[
                    row.opening_balance,
                    row.payment,
                    row.principal,
                    row.interest,
                    row.closing_balance,
                  ].map((val, vi) => (
                    <div key={vi} style={{ ...cellStyle(vi + 1), color: 'var(--fg-primary)' }}>
                      {formatAmount(val, { currency })}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function AccountScheduleSection({
  acctSchedule,
  accountName,
  currency,
}: {
  acctSchedule: DebtPlanScheduleByAccount
  accountName: string
  currency: string
}) {
  const [showAll, setShowAll] = useState(false)
  const rows = acctSchedule.rows
  const shouldVirtualize = rows.length > VIRTUALIZE_THRESHOLD
  const displayedRows = showAll || shouldVirtualize ? rows : rows.slice(0, INITIAL_SHOW)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>{accountName}</div>
      {shouldVirtualize ? (
        <VirtualizedScheduleTable rows={rows} currency={currency} />
      ) : (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          <div
            style={{
              display: 'flex',
              padding: '8px 12px',
              background: 'var(--bg-secondary)',
              borderBottom: '1px solid var(--border)',
            }}
          >
            {['Period', 'Opening', 'Payment', 'Principal', 'Interest', 'Closing'].map((col, i) => (
              <div
                key={col}
                style={{
                  flex: i === 0 ? '1.2' : '1',
                  textAlign: i === 0 ? 'left' : 'right',
                  fontSize: 11,
                  fontWeight: 500,
                  color: 'var(--fg-muted)',
                  paddingRight: 8,
                }}
              >
                {col}
              </div>
            ))}
          </div>
          {displayedRows.map((row, idx) => (
            <div
              key={row.id}
              style={{
                display: 'flex',
                padding: '8px 12px',
                background: row.is_payoff
                  ? 'color-mix(in oklch, var(--success) 10%, transparent)'
                  : idx % 2 === 0
                    ? 'transparent'
                    : 'color-mix(in oklch, var(--fg-primary) 2%, transparent)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div
                style={{
                  flex: '1.2',
                  fontSize: 12,
                  color: row.is_payoff ? 'var(--success)' : 'var(--fg-secondary)',
                  paddingRight: 8,
                }}
              >
                {formatDate(row.period_date)}
                {row.is_payoff ? ' ✓' : ''}
              </div>
              {[
                row.opening_balance,
                row.payment,
                row.principal,
                row.interest,
                row.closing_balance,
              ].map((val, vi) => (
                <div
                  key={vi}
                  style={{
                    flex: '1',
                    textAlign: 'right',
                    fontSize: 12,
                    fontFamily: "'Geist Mono', monospace",
                    color: 'var(--fg-primary)',
                    paddingRight: 8,
                  }}
                >
                  {formatAmount(val, { currency })}
                </div>
              ))}
            </div>
          ))}
          {!showAll && rows.length > INITIAL_SHOW && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 12px',
                background: 'none',
                border: 'none',
                borderTop: '1px solid var(--border)',
                color: 'var(--accent)',
                fontSize: 12,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              Show all {rows.length} months
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function RecordPaymentModal({
  householdId,
  accountId,
  accountName,
  onClose,
}: {
  householdId: string
  accountId: string
  accountName: string
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0] ?? '')
  const [error, setError] = useState<string | null>(null)

  const recordPayment =
    useRecordPaymentApiV1HouseholdsHouseholdIdDebtPlansAccountsAccountIdPaymentPost({
      mutation: {
        onSuccess: () => {
          void qc.invalidateQueries()
          onClose()
        },
        onError: () => setError('Failed to record payment'),
      },
    })

  function handleSubmit() {
    if (!amount || parseFloat(amount) <= 0) {
      setError('Enter a valid amount')
      return
    }
    recordPayment.mutate({
      householdId,
      accountId,
      data: { amount, payment_date: paymentDate },
    })
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 200,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: 24,
          width: 380,
          maxWidth: '95vw',
          boxShadow: 'var(--shadow)',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Record payment — {accountName}
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Amount
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              style={{
                padding: '7px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                fontFamily: "'Geist Mono', monospace",
                outline: 'none',
              }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Date
            </label>
            <input
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
              style={{
                padding: '7px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
          </div>
        </div>
        {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '7px 14px',
              fontSize: 13,
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--fg-secondary)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={recordPayment.isPending}
            onClick={handleSubmit}
            style={{
              padding: '7px 14px',
              fontSize: 13,
              fontWeight: 500,
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 8,
              color: 'var(--accent-fg)',
              cursor: recordPayment.isPending ? 'not-allowed' : 'pointer',
              opacity: recordPayment.isPending ? 0.7 : 1,
            }}
          >
            {recordPayment.isPending ? 'Recording...' : 'Record payment'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function DebtPlanPage() {
  const { planId } = useParams<{ planId: string }>()
  const navigate = useNavigate()
  const { householdId } = useHousehold()

  const [showAmortization, setShowAmortization] = useState(false)
  const [paymentAccountId, setPaymentAccountId] = useState<string | null>(null)

  const hid = householdId ?? ''
  const pid = planId ?? ''

  const { data: plan } = useGetPlanApiV1HouseholdsHouseholdIdDebtPlansPlanIdGet(hid, pid, {
    query: { enabled: !!hid && !!pid },
  })

  const { data: summary } = useGetSummaryApiV1HouseholdsHouseholdIdDebtPlansPlanIdSummaryGet(
    hid,
    pid,
    { query: { enabled: !!hid && !!pid } }
  )

  const { data: schedule = [] } =
    useGetScheduleApiV1HouseholdsHouseholdIdDebtPlansPlanIdScheduleGet(hid, pid, {
      query: { enabled: !!hid && !!pid && showAmortization },
    })

  const { data: allAccounts = [] } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    hid,
    undefined,
    { query: { enabled: !!hid } }
  )

  const liabilityAccounts = allAccounts.filter((a) => isLiabilityType(a.account_type))
  const acctById = new Map(liabilityAccounts.map((a) => [a.id, a]))
  const planAccounts = liabilityAccounts.filter(
    (a) => !plan?.account_ids?.length || (plan.account_ids as string[]).includes(a.id)
  )
  const paymentAccount = paymentAccountId ? acctById.get(paymentAccountId) : null

  if (!householdId || !planId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div
        style={{
          padding: '14px 24px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/debts')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            background: 'none',
            border: 'none',
            color: 'var(--fg-muted)',
            fontSize: 13,
            cursor: 'pointer',
            marginBottom: 10,
            padding: 0,
          }}
        >
          <ChevronLeft size={14} /> Debts
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div>
            <h1
              style={{
                fontSize: 22,
                fontWeight: 600,
                color: 'var(--fg-primary)',
                margin: '0 0 6px',
                letterSpacing: '-0.01em',
              }}
            >
              {plan?.name ?? 'Debt Plan'}
            </h1>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {plan && (
                <>
                  <Badge label={methodLabel(plan.method)} color="var(--accent)" />
                  {parseFloat(plan.monthly_extra_payment) > 0 && (
                    <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                      +{formatAmount(plan.monthly_extra_payment, { currency: plan.currency })}/mo
                      extra
                    </span>
                  )}
                  {plan.snowball_flow && <Badge label="Snowball flow" />}
                </>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {planAccounts.length > 0 && (
              <div style={{ position: 'relative' }}>
                <select
                  onChange={(e) => setPaymentAccountId(e.target.value || null)}
                  value={paymentAccountId ?? ''}
                  style={{
                    padding: '7px 12px',
                    background: 'none',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    color: 'var(--fg-secondary)',
                    fontSize: 13,
                    cursor: 'pointer',
                    appearance: 'none',
                    paddingRight: 28,
                  }}
                >
                  <option value="">Record payment...</option>
                  {planAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
                <CalendarCheck
                  size={13}
                  style={{
                    position: 'absolute',
                    right: 8,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none',
                    color: 'var(--fg-muted)',
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        {/* Summary panel */}
        {summary ? (
          <SummaryPanel summary={summary} currency={plan?.currency ?? 'USD'} />
        ) : (
          <div
            style={{
              padding: '20px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              color: 'var(--fg-muted)',
              fontSize: 13,
            }}
          >
            Computing payoff schedule... This may take a moment.
          </div>
        )}

        {/* Comparison */}
        {plan && (
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '16px 18px',
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--fg-primary)',
                marginBottom: 12,
              }}
            >
              Compare strategies
            </div>
            <ComparisonPanel householdId={hid} planId={pid} planCurrency={plan.currency} />
          </div>
        )}

        {/* Amortization table */}
        <div style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
          <button
            type="button"
            onClick={() => setShowAmortization((s) => !s)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 18px',
              background: 'var(--bg-elevated)',
              border: 'none',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--fg-secondary)',
            }}
          >
            Amortization schedule
            <ChevronDown
              size={14}
              style={{
                transform: showAmortization ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.2s',
              }}
            />
          </button>

          {showAmortization && (
            <div
              style={{
                borderTop: '1px solid var(--border)',
                padding: '16px 18px',
                display: 'flex',
                flexDirection: 'column',
                gap: 20,
              }}
            >
              {schedule.length === 0 ? (
                <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>
                  No schedule data. Run "Compute schedule" to generate it.
                </div>
              ) : (
                (schedule as DebtPlanScheduleByAccount[]).map((acctSchedule) => {
                  const acct = acctById.get(acctSchedule.account_id)
                  return (
                    <AccountScheduleSection
                      key={acctSchedule.account_id}
                      acctSchedule={acctSchedule}
                      accountName={acct?.name ?? acctSchedule.account_id}
                      currency={plan?.currency ?? 'USD'}
                    />
                  )
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* Record payment modal */}
      {paymentAccountId && paymentAccount && (
        <RecordPaymentModal
          householdId={hid}
          accountId={paymentAccountId}
          accountName={paymentAccount.name}
          onClose={() => setPaymentAccountId(null)}
        />
      )}
    </div>
  )
}
