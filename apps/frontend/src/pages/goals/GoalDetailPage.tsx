import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, Pause, Play, Pencil, Trash2, Plus, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import {
  useGetGoalApiV1HouseholdsHouseholdIdGoalsGoalIdGet,
  useGetGoalStatusApiV1HouseholdsHouseholdIdGoalsGoalIdStatusGet,
  useListGoalHistoryApiV1HouseholdsHouseholdIdGoalsGoalIdHistoryGet,
  useListContributionsApiV1HouseholdsHouseholdIdGoalsGoalIdContributionsGet,
  useListFundingSourcesApiV1HouseholdsHouseholdIdGoalsGoalIdFundingSourcesGet,
  usePauseGoalApiV1HouseholdsHouseholdIdGoalsGoalIdPausePost,
  useResumeGoalApiV1HouseholdsHouseholdIdGoalsGoalIdResumePost,
  useArchiveGoalApiV1HouseholdsHouseholdIdGoalsGoalIdDelete,
  useUpdateGoalApiV1HouseholdsHouseholdIdGoalsGoalIdPatch,
} from '@/api/generated/default/default'
import {
  useListMembersApiV1HouseholdsHouseholdIdMembersGet,
  useGetHouseholdApiV1HouseholdsHouseholdIdGet,
} from '@/api/generated/households/households'
import { useHousehold } from '@/hooks/use-household'
import { useGetFxRateApiV1FxRatesGet } from '@/api/generated/platform/platform'
import { formatAmount } from '@/lib/format-amount'
import { BurnUpStatus } from '@/api/generated/model/burnUpStatus'
import { GoalStatus } from '@/api/generated/model/goalStatus'
import { ContributionLogModal } from './ContributionLogModal'

function goalTypeLabel(type: string): string {
  const map: Record<string, string> = {
    savings_target: 'Savings Target',
    purchase: 'Purchase',
    debt_payoff: 'Debt Payoff',
    net_worth: 'Net Worth',
    category_reduction: 'Category Reduction',
    emergency_fund: 'Emergency Fund',
    recurring_contribution: 'Recurring Contribution',
    minimum_balance: 'Minimum Balance',
  }
  return map[type] ?? type
}

function burnUpColor(status: string): string {
  if (status === BurnUpStatus.ahead || status === BurnUpStatus.on_track) return 'var(--success)'
  if (status === BurnUpStatus.behind || status === BurnUpStatus.at_risk) return 'var(--warning)'
  return 'var(--danger)'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    ahead: 'Ahead',
    on_track: 'On Track',
    behind: 'Behind',
    at_risk: 'At Risk',
    off_track: 'Off Track',
  }
  return map[status] ?? status
}

function contributionTypeLabel(type: string): string {
  const map: Record<string, string> = {
    manual: 'Manual',
    tag_driven: 'Tag-driven',
    recurring_rule: 'Recurring',
  }
  return map[type] ?? type
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatShortDate(dateStr: string): string {
  const parts = dateStr.split('-')
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return `${m}/${d}`
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
        whiteSpace: 'nowrap' as const,
      }}
    >
      {label}
    </span>
  )
}

function StatCard({
  label,
  value,
  color,
  sub,
}: {
  label: string
  value: string
  color?: string
  sub?: string
}) {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '12px 16px',
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-muted)',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 20,
          fontWeight: 700,
          fontFamily: "'Geist Mono', monospace",
          color: color ?? 'var(--fg-primary)',
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export function GoalDetailPage() {
  const { goalId } = useParams<{ goalId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { householdId } = useHousehold()

  const [showContributionModal, setShowContributionModal] = useState(false)
  const [showConfirmArchive, setShowConfirmArchive] = useState(false)
  const [editName, setEditName] = useState(false)
  const [editNameValue, setEditNameValue] = useState('')

  const hid = householdId ?? ''
  const gid = goalId ?? ''

  const { data: goal, isLoading: goalLoading } = useGetGoalApiV1HouseholdsHouseholdIdGoalsGoalIdGet(
    hid,
    gid,
    {
      query: { enabled: !!hid && !!gid },
    }
  )

  const { data: snapshot } = useGetGoalStatusApiV1HouseholdsHouseholdIdGoalsGoalIdStatusGet(
    hid,
    gid,
    { query: { enabled: !!hid && !!gid } }
  )

  const { data: history = [] } = useListGoalHistoryApiV1HouseholdsHouseholdIdGoalsGoalIdHistoryGet(
    hid,
    gid,
    { query: { enabled: !!hid && !!gid } }
  )

  const { data: contributionData } =
    useListContributionsApiV1HouseholdsHouseholdIdGoalsGoalIdContributionsGet(hid, gid, {
      query: { enabled: !!hid && !!gid },
    })

  const { data: fundingSources = [] } =
    useListFundingSourcesApiV1HouseholdsHouseholdIdGoalsGoalIdFundingSourcesGet(hid, gid, {
      query: { enabled: !!hid && !!gid },
    })

  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(hid, {
    query: { enabled: !!hid },
  })

  const { data: household } = useGetHouseholdApiV1HouseholdsHouseholdIdGet(hid, {
    query: { enabled: !!hid },
  })
  const homeCurrency = household?.home_currency ?? 'USD'
  const todayStr = new Date().toISOString().split('T')[0] ?? new Date().toISOString().slice(0, 10)

  const isForeignGoal = !!goal && goal.currency !== homeCurrency
  const { data: fxRate } = useGetFxRateApiV1FxRatesGet(
    { from_currency: goal?.currency ?? 'USD', to_currency: homeCurrency, date: todayStr },
    { query: { enabled: isForeignGoal } }
  )

  const { mutate: pauseGoal, isPending: pausing } =
    usePauseGoalApiV1HouseholdsHouseholdIdGoalsGoalIdPausePost({
      mutation: { onSuccess: () => void qc.invalidateQueries() },
    })

  const { mutate: resumeGoal, isPending: resuming } =
    useResumeGoalApiV1HouseholdsHouseholdIdGoalsGoalIdResumePost({
      mutation: { onSuccess: () => void qc.invalidateQueries() },
    })

  const { mutate: archiveGoal, isPending: archiving } =
    useArchiveGoalApiV1HouseholdsHouseholdIdGoalsGoalIdDelete({
      mutation: {
        onSuccess: () => {
          void qc.invalidateQueries()
          navigate('/goals')
        },
      },
    })

  const { mutate: updateGoal } = useUpdateGoalApiV1HouseholdsHouseholdIdGoalsGoalIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries()
        setEditName(false)
      },
    },
  })

  if (!householdId || goalLoading) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  if (!goal) {
    return (
      <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Goal not found.</div>
    )
  }

  const currency = goal.currency
  const burnStatus = snapshot?.burn_up_status ?? null
  const targetAmount = goal.target_amount ? parseFloat(goal.target_amount) : null
  const cumulativeActual = snapshot ? parseFloat(snapshot.cumulative_actual) : 0
  const requiredPaceMonth = snapshot ? parseFloat(snapshot.required_pace) : null
  const actualPaceMonth = snapshot ? parseFloat(snapshot.actual_pace) : null
  const gapToClose = snapshot ? parseFloat(snapshot.gap_to_close) : null
  const projectedCompletion = snapshot?.projected_completion_date ?? null

  const ownerMember = goal.owner_id ? members.find((m) => m.user_id === goal.owner_id) : null

  const fxRateValue = fxRate ? parseFloat(fxRate.rate) : null
  const homeEquivActual =
    isForeignGoal && fxRateValue != null ? cumulativeActual * fxRateValue : null
  const homeEquivTarget =
    isForeignGoal && fxRateValue != null && targetAmount != null ? targetAmount * fxRateValue : null

  const chartData = history.map((s) => ({
    date: s.snapshot_date,
    actual: parseFloat(s.cumulative_actual),
    expected: parseFloat(s.cumulative_expected),
  }))

  const showProjectedLine =
    projectedCompletion && goal.target_date && projectedCompletion !== goal.target_date

  function getUserName(userId: string | null | undefined): string {
    if (!userId) return 'Household'
    return members.find((m) => m.user_id === userId)?.user.display_name ?? 'Unknown'
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '12px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <button
            type="button"
            onClick={() => navigate('/goals')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              background: 'none',
              border: 'none',
              color: 'var(--fg-muted)',
              cursor: 'pointer',
              fontSize: 13,
              padding: 0,
              flexShrink: 0,
            }}
          >
            <ChevronLeft size={16} />
            Goals
          </button>

          <span style={{ color: 'var(--border)', fontSize: 16 }}>/</span>

          {editName ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (editNameValue.trim()) {
                  updateGoal({
                    householdId: hid,
                    goalId: gid,
                    data: { name: editNameValue.trim() },
                  })
                }
              }}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <input
                autoFocus
                value={editNameValue}
                onChange={(e) => setEditNameValue(e.target.value)}
                style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: 'var(--fg-primary)',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--accent)',
                  borderRadius: 6,
                  padding: '2px 8px',
                  outline: 'none',
                  minWidth: 200,
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '4px 10px',
                  fontSize: 12,
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                }}
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setEditName(false)}
                style={{
                  padding: '4px 8px',
                  fontSize: 12,
                  background: 'none',
                  color: 'var(--fg-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  cursor: 'pointer',
                }}
              >
                <X size={12} />
              </button>
            </form>
          ) : (
            <h1
              style={{
                fontSize: 18,
                fontWeight: 600,
                color: 'var(--fg-primary)',
                margin: 0,
                letterSpacing: '-0.01em',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap' as const,
              }}
            >
              {goal.name}
            </h1>
          )}

          <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexShrink: 0 }}>
            <Badge label={goalTypeLabel(goal.goal_type)} color="var(--accent)" />
            {isForeignGoal && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: 99,
                  background: 'color-mix(in oklch, var(--warning, #f59e0b) 14%, transparent)',
                  color: '#f59e0b',
                  letterSpacing: '0.04em',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {currency}
              </span>
            )}
            {burnStatus && (
              <Badge label={statusLabel(burnStatus)} color={burnUpColor(burnStatus)} />
            )}
            {ownerMember && (
              <span
                style={{
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 99,
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-secondary)',
                  border: '1px solid var(--border)',
                }}
              >
                {ownerMember.user.display_name}
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            type="button"
            onClick={() => {
              setEditNameValue(goal.name)
              setEditName(true)
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '7px 12px',
              background: 'none',
              color: 'var(--fg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <Pencil size={13} />
            Edit
          </button>

          {goal.status === GoalStatus.active ? (
            <button
              type="button"
              disabled={pausing}
              onClick={() => pauseGoal({ householdId: hid, goalId: gid })}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '7px 12px',
                background: 'none',
                color: 'var(--warning)',
                border: '1px solid color-mix(in oklch, var(--warning) 40%, transparent)',
                borderRadius: 8,
                fontSize: 13,
                cursor: pausing ? 'not-allowed' : 'pointer',
                opacity: pausing ? 0.7 : 1,
              }}
            >
              <Pause size={13} />
              Pause
            </button>
          ) : goal.status === GoalStatus.paused ? (
            <button
              type="button"
              disabled={resuming}
              onClick={() => resumeGoal({ householdId: hid, goalId: gid })}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '7px 12px',
                background: 'none',
                color: 'var(--success)',
                border: '1px solid color-mix(in oklch, var(--success) 40%, transparent)',
                borderRadius: 8,
                fontSize: 13,
                cursor: resuming ? 'not-allowed' : 'pointer',
                opacity: resuming ? 0.7 : 1,
              }}
            >
              <Play size={13} />
              Resume
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => setShowConfirmArchive(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '7px 12px',
              background: 'none',
              color: 'var(--danger)',
              border: '1px solid color-mix(in oklch, var(--danger) 40%, transparent)',
              borderRadius: 8,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <Trash2 size={13} />
            Archive
          </button>
        </div>
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
        {/* Stats row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 10,
          }}
        >
          <StatCard
            label="Saved so far"
            value={formatAmount(cumulativeActual, { currency })}
            color={burnStatus ? burnUpColor(burnStatus) : undefined}
            sub={
              homeEquivActual != null
                ? `≈ ${formatAmount(homeEquivActual, { currency: homeCurrency })}${targetAmount ? ` · of ${formatAmount(targetAmount, { currency })}` : ''}${homeEquivTarget != null ? ` (≈ ${formatAmount(homeEquivTarget, { currency: homeCurrency })})` : ''}`
                : targetAmount
                  ? `of ${formatAmount(targetAmount, { currency })}`
                  : undefined
            }
          />
          {requiredPaceMonth != null && (
            <StatCard
              label="Required pace / mo"
              value={formatAmount(requiredPaceMonth, { currency })}
            />
          )}
          {actualPaceMonth != null && (
            <StatCard
              label="Actual pace / mo"
              value={formatAmount(actualPaceMonth, { currency })}
              color={
                requiredPaceMonth != null && actualPaceMonth >= requiredPaceMonth
                  ? 'var(--success)'
                  : 'var(--warning)'
              }
            />
          )}
          {gapToClose != null && Math.abs(gapToClose) > 0.01 && (
            <StatCard
              label="Gap to close"
              value={formatAmount(Math.abs(gapToClose), { currency })}
              color={gapToClose > 0 ? 'var(--danger)' : 'var(--success)'}
              sub={gapToClose > 0 ? 'behind expected' : 'ahead of pace'}
            />
          )}
          {goal.target_date && (
            <StatCard label="Target date" value={formatDate(goal.target_date)} />
          )}
          {projectedCompletion && (
            <StatCard
              label="Projected completion"
              value={formatDate(projectedCompletion)}
              color={showProjectedLine ? 'var(--warning)' : undefined}
            />
          )}
        </div>

        {/* Burn-up chart */}
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '18px 20px',
          }}
        >
          <div
            style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)', marginBottom: 4 }}
          >
            Progress
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 14 }}>
            Actual contributions vs required pace
          </div>

          {chartData.length === 0 ? (
            <div
              style={{
                height: 180,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              No history yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={(v: number) => formatAmount(v, { currency })}
                  tick={{ fontSize: 11, fill: 'var(--fg-muted)' }}
                  tickLine={false}
                  axisLine={false}
                  width={72}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 12,
                    color: 'var(--fg-primary)',
                  }}
                  formatter={(value: number, name: string) => [
                    formatAmount(value, { currency }),
                    name === 'actual' ? 'Actual' : 'Required pace',
                  ]}
                  labelFormatter={formatDate}
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  fill="var(--accent)"
                  fillOpacity={0.1}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="expected"
                  stroke="var(--fg-muted)"
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                  dot={false}
                  activeDot={{ r: 3 }}
                />
                {showProjectedLine && projectedCompletion && (
                  <ReferenceLine
                    x={projectedCompletion}
                    stroke="var(--warning)"
                    strokeDasharray="4 3"
                    label={{
                      value: 'Projected',
                      position: 'top',
                      fontSize: 10,
                      fill: 'var(--warning)',
                    }}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}

          <div
            style={{
              display: 'flex',
              gap: 16,
              marginTop: 10,
              fontSize: 11,
              color: 'var(--fg-muted)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div
                style={{
                  width: 16,
                  height: 2,
                  background: 'var(--accent)',
                  borderRadius: 1,
                }}
              />
              Actual
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div
                style={{
                  width: 16,
                  height: 2,
                  background: 'var(--fg-muted)',
                  borderRadius: 1,
                  borderTop: '2px dashed var(--fg-muted)',
                }}
              />
              Required pace
            </div>
          </div>
        </div>

        {/* Contributions */}
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '18px 20px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 14,
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
                Contributions
              </div>
              {contributionData && (
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                  Total:{' '}
                  <span style={{ color: 'var(--success)', fontWeight: 500 }}>
                    {formatAmount(parseFloat(contributionData.household_total), {
                      currency: contributionData.currency,
                    })}
                  </span>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => setShowContributionModal(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 12px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              <Plus size={12} />
              Log contribution
            </button>
          </div>

          {!contributionData || contributionData.contributions.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '12px 0' }}>
              No contributions yet
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {contributionData.contributions.map((c) => (
                <div
                  key={c.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 0',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 600,
                      fontFamily: "'Geist Mono', monospace",
                      color: 'var(--success)',
                      flexShrink: 0,
                    }}
                  >
                    +{formatAmount(parseFloat(c.amount), { currency: c.currency })}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                      {formatDate(c.contributed_at)}
                    </div>
                    {c.note && (
                      <div
                        style={{
                          fontSize: 12,
                          color: 'var(--fg-muted)',
                          fontStyle: 'italic',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap' as const,
                        }}
                      >
                        {c.note}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-muted)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      {contributionTypeLabel(c.contribution_type)}
                    </span>
                    {c.attributed_to_user_id && (
                      <span
                        style={{
                          fontSize: 11,
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: 'var(--bg-secondary)',
                          color: 'var(--fg-secondary)',
                          border: '1px solid var(--border)',
                        }}
                      >
                        {getUserName(c.attributed_to_user_id)}
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {contributionData.per_user.length > 0 && (
                <div
                  style={{
                    marginTop: 12,
                    paddingTop: 12,
                    borderTop: '1px solid var(--border)',
                    display: 'flex',
                    gap: 16,
                    flexWrap: 'wrap' as const,
                  }}
                >
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)', fontWeight: 500 }}>
                    Per member:
                  </div>
                  {contributionData.per_user.map((u) => (
                    <div
                      key={String(u.attributed_to_user_id)}
                      style={{ fontSize: 12, color: 'var(--fg-secondary)' }}
                    >
                      {getUserName(u.attributed_to_user_id)}{' '}
                      <span
                        style={{
                          fontFamily: "'Geist Mono', monospace",
                          color: 'var(--success)',
                          fontWeight: 600,
                        }}
                      >
                        {formatAmount(parseFloat(u.total), { currency: u.currency })}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Funding sources */}
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '18px 20px',
          }}
        >
          <div
            style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)', marginBottom: 12 }}
          >
            Funding sources
          </div>
          {fundingSources.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
              No funding sources configured
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {fundingSources.map((fs) => (
                <div
                  key={fs.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    fontSize: 13,
                    color: 'var(--fg-secondary)',
                  }}
                >
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      background: 'var(--bg-secondary)',
                      color: 'var(--fg-muted)',
                      border: '1px solid var(--border)',
                      fontSize: 11,
                    }}
                  >
                    {fs.source_type.replace('_', ' ')}
                  </span>
                  {fs.attributed_to_user_id && (
                    <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                      {getUserName(fs.attributed_to_user_id)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showContributionModal && (
        <ContributionLogModal
          householdId={hid}
          goalId={gid}
          currency={currency}
          onClose={() => setShowContributionModal(false)}
        />
      )}

      {showConfirmArchive && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
            background: 'rgba(0,0,0,0.42)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
          onClick={() => setShowConfirmArchive(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 380,
              maxWidth: '100%',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderTop: '2px solid var(--danger)',
              borderRadius: 14,
              padding: '24px',
              boxShadow: '0 24px 64px -12px rgba(0,0,0,0.45)',
            }}
          >
            <div
              style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)', marginBottom: 8 }}
            >
              Archive goal?
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-secondary)', marginBottom: 20 }}>
              This will archive &quot;{goal.name}&quot;. You can view it later but it will no longer
              be tracked actively.
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={() => setShowConfirmArchive(false)}
                style={{
                  padding: '8px 14px',
                  fontSize: 13,
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--fg-secondary)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={archiving}
                onClick={() => archiveGoal({ householdId: hid, goalId: gid })}
                style={{
                  padding: '8px 14px',
                  fontSize: 13,
                  fontWeight: 600,
                  borderRadius: 6,
                  border: 'none',
                  background: 'var(--danger)',
                  color: 'white',
                  cursor: archiving ? 'not-allowed' : 'pointer',
                  opacity: archiving ? 0.7 : 1,
                }}
              >
                {archiving ? 'Archiving...' : 'Archive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
