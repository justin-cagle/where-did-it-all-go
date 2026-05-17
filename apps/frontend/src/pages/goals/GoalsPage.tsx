import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, ChevronDown, ChevronRight } from 'lucide-react'
import {
  useListGoalsApiV1HouseholdsHouseholdIdGoalsGet,
  useGetGoalStatusApiV1HouseholdsHouseholdIdGoalsGoalIdStatusGet,
} from '@/api/generated/default/default'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import type { GoalOut } from '@/api/generated/model/goalOut'
import { GoalStatus } from '@/api/generated/model/goalStatus'
import { BurnUpStatus } from '@/api/generated/model/burnUpStatus'
import { GoalSetupModal } from './GoalSetupModal'

function goalTypeLabel(type: string): string {
  const map: Record<string, string> = {
    savings_target: 'Savings Target',
    purchase: 'Purchase',
    debt_payoff: 'Debt Payoff',
    net_worth: 'Net Worth',
    category_reduction: 'Category Reduction',
    emergency_fund: 'Emergency Fund',
    recurring_contribution: 'Recurring',
    minimum_balance: 'Min Balance',
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

function daysFromNow(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  const target = new Date(y, m - 1, d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.ceil((target.getTime() - today.getTime()) / 86400000)
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

function GoalCard({
  goal,
  householdId,
  onClick,
}: {
  goal: GoalOut
  householdId: string
  onClick: () => void
}) {
  const { data: snapshot } = useGetGoalStatusApiV1HouseholdsHouseholdIdGoalsGoalIdStatusGet(
    householdId,
    goal.id,
    { query: { enabled: !!householdId } }
  )

  const targetAmount = goal.target_amount ? parseFloat(goal.target_amount) : null
  const cumulativeActual = snapshot ? parseFloat(snapshot.cumulative_actual) : null
  const progressPct = snapshot ? parseFloat(snapshot.progress_pct) : null
  const burnUpStatus = snapshot?.burn_up_status ?? null
  const projectedCompletion = snapshot?.projected_completion_date ?? null
  const days = daysFromNow(goal.target_date ?? null)

  const barColor = burnUpStatus ? burnUpColor(burnUpStatus) : 'var(--accent)'
  const displayPct = progressPct != null ? Math.min(100, Math.round(progressPct)) : null

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
        gap: 12,
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
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            flex: 1,
            minWidth: 0,
          }}
        >
          {goal.name}
        </div>
        <div
          style={{
            display: 'flex',
            gap: 5,
            flexShrink: 0,
            flexWrap: 'wrap',
            justifyContent: 'flex-end',
          }}
        >
          <Badge label={goalTypeLabel(goal.goal_type)} color="var(--accent)" />
          {burnUpStatus && (
            <Badge label={statusLabel(burnUpStatus)} color={burnUpColor(burnUpStatus)} />
          )}
        </div>
      </div>

      {targetAmount != null && cumulativeActual != null ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              gap: 8,
            }}
          >
            <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
              {formatAmount(cumulativeActual, { currency: goal.currency })} of{' '}
              {formatAmount(targetAmount, { currency: goal.currency })}
            </div>
            {displayPct != null && (
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: barColor,
                  fontFamily: "'Geist Mono', monospace",
                  flexShrink: 0,
                }}
              >
                {displayPct}%
              </span>
            )}
          </div>

          <div
            style={{ height: 6, borderRadius: 99, background: 'var(--border)', overflow: 'hidden' }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, displayPct ?? 0)}%`,
                borderRadius: 99,
                background: barColor,
                transition: 'width 0.4s ease',
              }}
            />
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {projectedCompletion && (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--fg-muted)',
                  fontStyle:
                    goal.target_date && projectedCompletion !== goal.target_date
                      ? 'italic'
                      : 'normal',
                }}
              >
                Projected: {formatDate(projectedCompletion)}
              </div>
            )}
            {days != null && (
              <div
                style={{
                  fontSize: 12,
                  color: days < 0 ? 'var(--danger)' : 'var(--fg-muted)',
                  marginLeft: 'auto',
                  flexShrink: 0,
                }}
              >
                {days < 0
                  ? `${Math.abs(days)} days overdue`
                  : days === 0
                    ? 'Due today'
                    : `${days} days to go`}
              </div>
            )}
          </div>
        </div>
      ) : snapshot ? (
        <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
          {formatAmount(parseFloat(snapshot.cumulative_actual), { currency: goal.currency })}{' '}
          contributed
        </div>
      ) : (
        <div style={{ height: 48, background: 'var(--bg-secondary)', borderRadius: 8 }} />
      )}

      {goal.target_date && (
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          Target date: {formatDate(goal.target_date)}
        </div>
      )}
    </div>
  )
}

function GoalGroup({
  title,
  goals,
  householdId,
  defaultOpen = false,
  onGoalClick,
  emptyMsg,
}: {
  title: string
  goals: GoalOut[]
  householdId: string
  defaultOpen?: boolean
  onGoalClick: (id: string) => void
  emptyMsg: string
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '4px 0',
        }}
      >
        {open ? (
          <ChevronDown size={14} style={{ color: 'var(--fg-muted)' }} />
        ) : (
          <ChevronRight size={14} style={{ color: 'var(--fg-muted)' }} />
        )}
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase' as const,
            letterSpacing: '0.06em',
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            background: 'var(--bg-secondary)',
            padding: '1px 6px',
            borderRadius: 99,
            marginLeft: 2,
          }}
        >
          {goals.length}
        </span>
      </button>

      {open && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: 12,
          }}
        >
          {goals.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '12px 0' }}>
              {emptyMsg}
            </div>
          ) : (
            goals.map((g) => (
              <GoalCard
                key={g.id}
                goal={g}
                householdId={householdId}
                onClick={() => onGoalClick(g.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

export function GoalsPage() {
  const { householdId } = useHousehold()
  const navigate = useNavigate()
  const [showSetup, setShowSetup] = useState(false)

  const hid = householdId ?? ''

  const { data: goals = [], isLoading } = useListGoalsApiV1HouseholdsHouseholdIdGoalsGet(
    hid,
    undefined,
    { query: { enabled: !!hid } }
  )

  const activeGoals = goals.filter((g) => g.status === GoalStatus.active)
  const pausedGoals = goals.filter((g) => g.status === GoalStatus.paused)
  const completedGoals = goals.filter((g) => g.status === GoalStatus.completed)

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
          Goals
        </h1>
        <button
          type="button"
          onClick={() => setShowSetup(true)}
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
          Add goal
        </button>
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
        {isLoading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
        ) : goals.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              padding: '80px 24px',
              textAlign: 'center' as const,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              No goals yet
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
              Create your first goal to start tracking progress
            </div>
            <button
              type="button"
              onClick={() => setShowSetup(true)}
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
              Create goal
            </button>
          </div>
        ) : (
          <>
            <GoalGroup
              title="Active"
              goals={activeGoals}
              householdId={hid}
              defaultOpen
              onGoalClick={(id) => navigate(`/goals/${id}`)}
              emptyMsg="No active goals"
            />
            <GoalGroup
              title="Paused"
              goals={pausedGoals}
              householdId={hid}
              onGoalClick={(id) => navigate(`/goals/${id}`)}
              emptyMsg="No paused goals"
            />
            <GoalGroup
              title="Completed"
              goals={completedGoals}
              householdId={hid}
              onGoalClick={(id) => navigate(`/goals/${id}`)}
              emptyMsg="No completed goals"
            />
          </>
        )}
      </div>

      {showSetup && (
        <GoalSetupModal
          householdId={hid}
          onClose={() => setShowSetup(false)}
          onCreated={(id) => {
            setShowSetup(false)
            navigate(`/goals/${id}`)
          }}
        />
      )}
    </div>
  )
}
