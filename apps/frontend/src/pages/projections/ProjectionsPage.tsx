import { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import {
  useGetBalanceCurveApiV1HouseholdsHouseholdIdProjectionsBalanceCurveGet,
  useGetCashflowApiV1HouseholdsHouseholdIdProjectionsCashflowGet,
  useGetNetWorthApiV1HouseholdsHouseholdIdProjectionsNetWorthGet,
  useListBreachesApiV1HouseholdsHouseholdIdProjectionsBreachesGet,
  useGetProjectionApiV1HouseholdsHouseholdIdProjectionsGet,
} from '@/api/generated/default/default'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import { useListGoalsApiV1HouseholdsHouseholdIdGoalsGet } from '@/api/generated/default/default'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import type { AccountOut } from '@/api/generated/model/accountOut'
import type { BalancePoint } from '@/api/generated/model/balancePoint'
import type { CashflowPeriod } from '@/api/generated/model/cashflowPeriod'
import type { NetWorthPoint } from '@/api/generated/model/netWorthPoint'
import type { ProjectionBreachEventOut } from '@/api/generated/model/projectionBreachEventOut'
import { ScenariosPanel } from './ScenariosPanel'

type Tab = 'balance' | 'cashflow' | 'networth' | 'scenarios'

const HORIZON_OPTIONS = [3, 6, 12, 24] as const
type HorizonMonths = (typeof HORIZON_OPTIONS)[number]

const ACCOUNT_COLORS = [
  'var(--accent)',
  'var(--success)',
  'var(--info)',
  'var(--category-3)',
  'var(--category-4)',
  'var(--category-5)',
  'var(--category-6)',
]

function getDateRange(horizonMonths: number): { from: string; to: string } {
  const now = new Date()
  const from = now.toISOString().split('T')[0] ?? ''
  const target = new Date(now.getFullYear(), now.getMonth() + horizonMonths, now.getDate())
  const to = target.toISOString().split('T')[0] ?? ''
  return { from, to }
}

function formatMonthLabel(dateStr: string): string {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div
      style={{
        height: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--fg-muted)',
        fontSize: 13,
        background: 'var(--bg-secondary)',
        borderRadius: 8,
      }}
    >
      {message}
    </div>
  )
}

function SkeletonChart() {
  return (
    <div
      style={{
        height: 300,
        background: 'var(--bg-secondary)',
        borderRadius: 8,
        animation: 'pulse 1.5s ease-in-out infinite',
      }}
    />
  )
}

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'balance', label: 'Balance' },
    { id: 'cashflow', label: 'Cash Flow' },
    { id: 'networth', label: 'Net Worth' },
    { id: 'scenarios', label: 'Scenarios' },
  ]
  return (
    <div
      style={{
        display: 'flex',
        gap: 2,
        borderBottom: '1px solid var(--border)',
        marginBottom: 20,
      }}
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          style={{
            padding: '10px 16px',
            background: 'none',
            border: 'none',
            borderBottom: active === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            color: active === t.id ? 'var(--accent)' : 'var(--fg-muted)',
            fontSize: 13,
            fontWeight: active === t.id ? 600 : 400,
            cursor: 'pointer',
            marginBottom: -1,
            transition: 'color 0.1s',
            fontFamily: 'var(--font-sans)',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

function HorizonSlider({
  value,
  onChange,
}: {
  value: HorizonMonths
  onChange: (v: HorizonMonths) => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 12, color: 'var(--fg-muted)', marginRight: 4 }}>Horizon:</span>
      {HORIZON_OPTIONS.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          style={{
            padding: '4px 10px',
            fontSize: 12,
            borderRadius: 6,
            border: `1px solid ${value === m ? 'var(--accent)' : 'var(--border)'}`,
            background:
              value === m ? 'color-mix(in oklch, var(--accent) 12%, transparent)' : 'none',
            color: value === m ? 'var(--accent)' : 'var(--fg-muted)',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          {m}mo
        </button>
      ))}
    </div>
  )
}

function BalanceTab({
  householdId,
  horizon,
  onHorizonChange,
}: {
  householdId: string
  horizon: HorizonMonths
  onHorizonChange: (v: HorizonMonths) => void
}) {
  const { from, to } = getDateRange(horizon)
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])

  const { data: accounts = [] } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    householdId,
    undefined,
    { query: { enabled: !!householdId } }
  )

  const accountsParam = selectedAccounts.length > 0 ? selectedAccounts.join(',') : undefined

  const { data: points = [], isLoading } =
    useGetBalanceCurveApiV1HouseholdsHouseholdIdProjectionsBalanceCurveGet(
      householdId,
      { accounts: accountsParam, from, to },
      { query: { enabled: !!householdId } }
    )

  const { data: breaches = [] } = useListBreachesApiV1HouseholdsHouseholdIdProjectionsBreachesGet(
    householdId,
    {},
    { query: { enabled: !!householdId } }
  )

  const accountMap = useMemo(() => {
    const m = new Map<string, AccountOut>()
    accounts.forEach((a) => m.set(a.id, a))
    return m
  }, [accounts])

  const visibleAccountIds = useMemo(() => {
    const ids = Array.from(new Set((points as BalancePoint[]).map((p) => p.account_id)))
    return ids
  }, [points])

  const chartData = useMemo(() => {
    const byDate = new Map<string, Record<string, number>>()
    ;(points as BalancePoint[]).forEach((p) => {
      const row = byDate.get(p.event_date) ?? {}
      row[p.account_id] = parseFloat(p.balance)
      byDate.set(p.event_date, row)
    })
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date, label: formatMonthLabel(date), ...vals }))
  }, [points])

  const breachDates = useMemo(() => {
    return (breaches as ProjectionBreachEventOut[]).filter(
      (b) => b.breach_date >= from && b.breach_date <= to
    )
  }, [breaches, from, to])

  const toggleAccount = (id: string) => {
    setSelectedAccounts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const currency = accounts[0]?.currency ?? 'USD'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {accounts.map((a) => {
            const selected = selectedAccounts.length === 0 || selectedAccounts.includes(a.id)
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => toggleAccount(a.id)}
                style={{
                  padding: '4px 10px',
                  fontSize: 12,
                  borderRadius: 99,
                  border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
                  background: selected
                    ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                    : 'none',
                  color: selected ? 'var(--accent)' : 'var(--fg-muted)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                {a.name}
              </button>
            )
          })}
        </div>
        <HorizonSlider value={horizon} onChange={onHorizonChange} />
      </div>

      {isLoading ? (
        <SkeletonChart />
      ) : chartData.length === 0 ? (
        <EmptyChart message="No projection data" />
      ) : (
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => formatAmount(v, { currency, compact: true })}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number, name: string) => [
                  formatAmount(value, { currency }),
                  accountMap.get(name)?.name ?? name,
                ]}
              />
              <Legend
                formatter={(id: string) => accountMap.get(id)?.name ?? id}
                wrapperStyle={{ fontSize: 12 }}
              />
              {visibleAccountIds.map((id, i) => {
                const acct = accountMap.get(id)
                const isLiability =
                  acct?.account_type === 'credit_card' ||
                  acct?.account_type === 'loan' ||
                  acct?.account_type === 'line_of_credit'
                return (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={id}
                    name={id}
                    stroke={
                      isLiability
                        ? 'var(--danger)'
                        : (ACCOUNT_COLORS[i % ACCOUNT_COLORS.length] ?? 'var(--accent)')
                    }
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                )
              })}
              {breachDates.map((b) => (
                <ReferenceLine
                  key={b.id}
                  x={formatMonthLabel(b.breach_date)}
                  stroke="var(--warning)"
                  strokeDasharray="4 3"
                  label={{
                    value: b.breach_type.replace(/_/g, ' '),
                    fill: 'var(--warning)',
                    fontSize: 10,
                  }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {breachDates.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--fg-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Breach Events
          </div>
          {breachDates.map((b) => (
            <div
              key={b.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                background: 'color-mix(in oklch, var(--warning) 10%, transparent)',
                border: '1px solid color-mix(in oklch, var(--warning) 30%, transparent)',
                borderRadius: 8,
                fontSize: 12,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: 'var(--warning)',
                  flexShrink: 0,
                }}
              />
              <span style={{ color: 'var(--fg-primary)', fontWeight: 500 }}>
                {b.breach_type.replace(/_/g, ' ')}
              </span>
              <span style={{ color: 'var(--fg-muted)' }}>{formatMonthLabel(b.breach_date)}</span>
              {b.description && (
                <span style={{ color: 'var(--fg-muted)' }}>&mdash; {String(b.description)}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CashFlowTab({
  householdId,
  horizon,
  onHorizonChange,
}: {
  householdId: string
  horizon: HorizonMonths
  onHorizonChange: (v: HorizonMonths) => void
}) {
  const { from, to } = getDateRange(horizon)
  const [period, setPeriod] = useState<'monthly' | 'weekly'>('monthly')

  const { data: periods = [], isLoading } =
    useGetCashflowApiV1HouseholdsHouseholdIdProjectionsCashflowGet(
      householdId,
      { from, to, period },
      { query: { enabled: !!householdId } }
    )

  const chartData = useMemo(() => {
    return (periods as CashflowPeriod[]).map((p) => ({
      label: formatMonthLabel(p.period_start),
      income: parseFloat(p.total_income),
      expenses: parseFloat(p.total_expenses),
      net: parseFloat(p.net_cashflow),
    }))
  }, [periods])

  const currency = (periods as CashflowPeriod[])[0]?.currency ?? 'USD'

  const avgIncome =
    chartData.length > 0 ? chartData.reduce((s, r) => s + r.income, 0) / chartData.length : 0
  const avgExpenses =
    chartData.length > 0 ? chartData.reduce((s, r) => s + r.expenses, 0) / chartData.length : 0
  const avgNet = avgIncome - avgExpenses

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', gap: 4 }}>
          {(['monthly', 'weekly'] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                borderRadius: 6,
                border: `1px solid ${period === p ? 'var(--accent)' : 'var(--border)'}`,
                background:
                  period === p ? 'color-mix(in oklch, var(--accent) 12%, transparent)' : 'none',
                color: period === p ? 'var(--accent)' : 'var(--fg-muted)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
        <HorizonSlider value={horizon} onChange={onHorizonChange} />
      </div>

      {isLoading ? (
        <SkeletonChart />
      ) : chartData.length === 0 ? (
        <EmptyChart message="No projection data" />
      ) : (
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => formatAmount(v, { currency, compact: true })}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number, name: string) => [
                  formatAmount(value, { currency }),
                  name.charAt(0).toUpperCase() + name.slice(1),
                ]}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar
                dataKey="income"
                name="Income"
                fill="var(--success)"
                fillOpacity={0.7}
                radius={[3, 3, 0, 0]}
              />
              <Bar
                dataKey="expenses"
                name="Expenses"
                fill="var(--danger)"
                fillOpacity={0.6}
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {chartData.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          {[
            { label: 'Avg monthly income', value: avgIncome, color: 'var(--success)' },
            { label: 'Avg monthly expenses', value: avgExpenses, color: 'var(--danger)' },
            {
              label: 'Avg net',
              value: avgNet,
              color: avgNet >= 0 ? 'var(--success)' : 'var(--danger)',
            },
            {
              label: 'Projected annual savings',
              value: avgNet * 12,
              color: avgNet >= 0 ? 'var(--success)' : 'var(--danger)',
            },
          ].map((s) => (
            <div
              key={s.label}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '12px 14px',
              }}
            >
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 4 }}>
                {s.label}
              </div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: s.color,
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '-0.02em',
                }}
              >
                {formatAmount(s.value, { currency })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NetWorthTab({
  householdId,
  horizon,
  onHorizonChange,
}: {
  householdId: string
  horizon: HorizonMonths
  onHorizonChange: (v: HorizonMonths) => void
}) {
  const { from, to } = getDateRange(horizon)

  const { data: points = [], isLoading } =
    useGetNetWorthApiV1HouseholdsHouseholdIdProjectionsNetWorthGet(
      householdId,
      { from, to },
      { query: { enabled: !!householdId } }
    )

  const { data: goals = [] } = useListGoalsApiV1HouseholdsHouseholdIdGoalsGet(
    householdId,
    undefined,
    { query: { enabled: !!householdId } }
  )

  const chartData = useMemo(() => {
    return (points as NetWorthPoint[]).map((p) => ({
      date: p.event_date,
      label: formatMonthLabel(p.event_date),
      netWorth: parseFloat(p.net_worth),
    }))
  }, [points])

  const currency = (points as NetWorthPoint[])[0]?.currency ?? 'USD'
  const first = chartData[0]?.netWorth ?? null
  const last = chartData[chartData.length - 1]?.netWorth ?? null
  const delta = first != null && last != null ? last - first : null

  const goalMilestones = useMemo(() => {
    return goals
      .filter((g) => g.target_date && g.target_date >= from && g.target_date <= to)
      .map((g) => ({
        label: formatMonthLabel(g.target_date ?? ''),
        name: g.name,
      }))
  }, [goals, from, to])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <HorizonSlider value={horizon} onChange={onHorizonChange} />
      </div>

      {last != null && (
        <div style={{ display: 'flex', gap: 16 }}>
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: '14px 18px',
            }}
          >
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 4 }}>
              Current net worth
            </div>
            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                color: 'var(--fg-primary)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '-0.02em',
              }}
            >
              {formatAmount(first ?? 0, { currency })}
            </div>
          </div>
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: '14px 18px',
            }}
          >
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 4 }}>
              At {horizon}mo horizon
            </div>
            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                color: 'var(--fg-primary)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '-0.02em',
              }}
            >
              {formatAmount(last, { currency })}
            </div>
            {delta != null && (
              <div
                style={{
                  fontSize: 12,
                  color: delta >= 0 ? 'var(--success)' : 'var(--danger)',
                  marginTop: 2,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {delta >= 0 ? '+' : ''}
                {formatAmount(delta, { currency })}
              </div>
            )}
          </div>
        </div>
      )}

      {isLoading ? (
        <SkeletonChart />
      ) : chartData.length === 0 ? (
        <EmptyChart message="No projection data" />
      ) : (
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="nw-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => formatAmount(v, { currency, compact: true })}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number) => [formatAmount(value, { currency }), 'Net Worth']}
              />
              <Area
                type="monotone"
                dataKey="netWorth"
                name="Net Worth"
                stroke="var(--accent)"
                strokeWidth={2}
                fill="url(#nw-fill)"
                dot={false}
                activeDot={{ r: 4 }}
              />
              {goalMilestones.map((g, i) => (
                <ReferenceLine
                  key={i}
                  x={g.label}
                  stroke="var(--success)"
                  strokeDasharray="3 3"
                  label={{ value: `* ${g.name}`, fill: 'var(--success)', fontSize: 10 }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export function ProjectionsPage() {
  const { householdId } = useHousehold()
  const [activeTab, setActiveTab] = useState<Tab>('balance')
  const [horizon, setHorizon] = useState<HorizonMonths>(12)

  const hid = householdId ?? ''

  const { data: projection } = useGetProjectionApiV1HouseholdsHouseholdIdProjectionsGet(
    hid,
    { horizon_months: horizon },
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
        <div>
          <h1
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            Projections
          </h1>
          {projection && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              Computed {new Date(projection.run.computed_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        <TabBar active={activeTab} onChange={setActiveTab} />

        {activeTab === 'balance' && (
          <BalanceTab householdId={hid} horizon={horizon} onHorizonChange={setHorizon} />
        )}
        {activeTab === 'cashflow' && (
          <CashFlowTab householdId={hid} horizon={horizon} onHorizonChange={setHorizon} />
        )}
        {activeTab === 'networth' && (
          <NetWorthTab householdId={hid} horizon={horizon} onHorizonChange={setHorizon} />
        )}
        {activeTab === 'scenarios' && <ScenariosPanel householdId={hid} />}
      </div>
    </div>
  )
}
