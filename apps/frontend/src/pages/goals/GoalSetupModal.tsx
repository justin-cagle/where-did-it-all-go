import { useState } from 'react'
import {
  X,
  Target,
  ShoppingBag,
  CreditCard,
  Shield,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useCreateGoalApiV1HouseholdsHouseholdIdGoalsPost } from '@/api/generated/default/default'
import { useListPlansApiV1HouseholdsHouseholdIdDebtPlansGet } from '@/api/generated/default/default'
import { useListMembersApiV1HouseholdsHouseholdIdMembersGet } from '@/api/generated/households/households'
import { useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet } from '@/api/generated/classification/classification'
import { CategorySelect } from '@/components/CategorySelect'
import type { GoalType } from '@/api/generated/model/goalType'
import { CompletionPolicy } from '@/api/generated/model/completionPolicy'

interface Props {
  householdId: string
  onClose: () => void
  onCreated: (goalId: string) => void
}

type GoalTypeName = GoalType

interface GoalTypeConfig {
  type: GoalTypeName
  label: string
  description: string
  icon: React.ReactNode
}

const GOAL_TYPES: GoalTypeConfig[] = [
  {
    type: 'savings_target',
    label: 'Savings Target',
    description: 'Save toward a target amount',
    icon: <Target size={20} />,
  },
  {
    type: 'purchase',
    label: 'Purchase',
    description: 'Save for a specific purchase',
    icon: <ShoppingBag size={20} />,
  },
  {
    type: 'debt_payoff',
    label: 'Debt Payoff',
    description: 'Track paying off a debt',
    icon: <CreditCard size={20} />,
  },
  {
    type: 'emergency_fund',
    label: 'Emergency Fund',
    description: 'Build your safety net',
    icon: <Shield size={20} />,
  },
  {
    type: 'recurring_contribution',
    label: 'Recurring Contribution',
    description: 'Contribute on a schedule',
    icon: <RefreshCw size={20} />,
  },
  {
    type: 'category_reduction',
    label: 'Category Reduction',
    description: 'Spend less on a category',
    icon: <TrendingDown size={20} />,
  },
  {
    type: 'net_worth',
    label: 'Net Worth',
    description: 'Grow your net worth to a target',
    icon: <TrendingUp size={20} />,
  },
  {
    type: 'minimum_balance',
    label: 'Minimum Balance',
    description: 'Keep an account above a threshold',
    icon: <Wallet size={20} />,
  },
]

const COMPLETION_POLICIES = [
  {
    value: CompletionPolicy.prompt_on_complete,
    label: 'Prompt on complete',
    description: 'Ask what to do when goal is reached (default)',
  },
  {
    value: CompletionPolicy.archive_on_complete,
    label: 'Archive on complete',
    description: 'Automatically archive when target is hit',
  },
  {
    value: CompletionPolicy.auto_extend,
    label: 'Auto-extend',
    description: 'Increment target and continue',
  },
  {
    value: CompletionPolicy.auto_clone,
    label: 'Auto-clone',
    description: 'Start a fresh copy when complete',
  },
  {
    value: CompletionPolicy.convert_to_recurring,
    label: 'Convert to recurring',
    description: 'Become a recurring contribution goal',
  },
]

function needsTargetAmount(type: GoalTypeName): boolean {
  return [
    'savings_target',
    'purchase',
    'emergency_fund',
    'category_reduction',
    'net_worth',
  ].includes(type)
}

function needsDebtPlan(type: GoalTypeName): boolean {
  return type === 'debt_payoff'
}

function needsCategory(type: GoalTypeName): boolean {
  return type === 'category_reduction'
}

function needsMinBalance(type: GoalTypeName): boolean {
  return type === 'minimum_balance'
}

function targetDateRequired(type: GoalTypeName): boolean {
  return type === 'purchase'
}

export function GoalSetupModal({ householdId, onClose, onCreated }: Props) {
  const qc = useQueryClient()
  const [selectedType, setSelectedType] = useState<GoalTypeName | null>(null)

  const [name, setName] = useState('')
  const [targetAmount, setTargetAmount] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [targetDate, setTargetDate] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [completionPolicy, setCompletionPolicy] = useState<string>(
    CompletionPolicy.prompt_on_complete
  )
  const [linkedDebtPlanId, setLinkedDebtPlanId] = useState('')
  const [linkedCategoryId, setLinkedCategoryId] = useState<string | null>(null)
  const [minBalanceThreshold, setMinBalanceThreshold] = useState('')
  const [error, setError] = useState('')

  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(householdId, {
    query: { enabled: !!householdId },
  })

  const { data: debtPlans = [] } = useListPlansApiV1HouseholdsHouseholdIdDebtPlansGet(householdId, {
    query: { enabled: !!householdId && selectedType === 'debt_payoff' },
  })

  const { data: categories = [] } = useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet(
    householdId,
    {
      query: { enabled: !!householdId && selectedType === 'category_reduction' },
    }
  )

  const { mutate: createGoal, isPending } = useCreateGoalApiV1HouseholdsHouseholdIdGoalsPost({
    mutation: {
      onSuccess: (data) => {
        void qc.invalidateQueries()
        onCreated(data.id)
      },
      onError: () => {
        setError('Failed to create goal. Please try again.')
      },
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedType) return
    if (!name.trim()) {
      setError('Name is required.')
      return
    }
    if (targetDateRequired(selectedType) && !targetDate) {
      setError('Target date is required for purchase goals.')
      return
    }
    setError('')

    createGoal({
      householdId,
      data: {
        name: name.trim(),
        goal_type: selectedType,
        currency,
        target_amount: needsTargetAmount(selectedType) && targetAmount ? targetAmount : undefined,
        target_date: targetDate || undefined,
        completion_policy:
          completionPolicy as (typeof CompletionPolicy)[keyof typeof CompletionPolicy],
        owner_id: ownerId || undefined,
        linked_debt_plan_id: linkedDebtPlanId || undefined,
        linked_category_id: linkedCategoryId || undefined,
        minimum_balance_threshold:
          needsMinBalance(selectedType) && minBalanceThreshold ? minBalanceThreshold : undefined,
      },
    })
  }

  function inputStyle(): React.CSSProperties {
    return {
      padding: '8px 10px',
      borderRadius: 8,
      border: '1px solid var(--border)',
      background: 'var(--bg-elevated)',
      color: 'var(--fg-primary)',
      fontSize: 13,
      outline: 'none',
      width: '100%',
    }
  }

  function labelStyle(): React.CSSProperties {
    return {
      fontSize: 12,
      fontWeight: 500,
      color: 'var(--fg-secondary)',
      marginBottom: 4,
      display: 'block',
    }
  }

  if (!selectedType) {
    return (
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
        onClick={onClose}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 540,
            maxWidth: '100%',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderTop: '2px solid var(--accent)',
            borderRadius: 14,
            boxShadow: '0 24px 64px -12px rgba(0,0,0,0.45)',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '88vh',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '18px 22px 14px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexShrink: 0,
            }}
          >
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
                Choose goal type
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                Select the kind of goal you want to create
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              style={{
                width: 26,
                height: 26,
                border: '1px solid var(--border)',
                background: 'transparent',
                borderRadius: 6,
                color: 'var(--fg-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
              }}
            >
              <X size={13} />
            </button>
          </div>

          <div
            style={{
              padding: '16px 22px 22px',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 10,
              overflowY: 'auto',
            }}
          >
            {GOAL_TYPES.map((gt) => (
              <button
                key={gt.type}
                type="button"
                onClick={() => setSelectedType(gt.type)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  padding: '14px 16px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 10,
                  cursor: 'pointer',
                  textAlign: 'left' as const,
                  transition: 'border-color 0.15s, box-shadow 0.15s',
                }}
                onMouseEnter={(e) => {
                  const el = e.currentTarget
                  el.style.borderColor = 'var(--accent)'
                  el.style.boxShadow =
                    '0 0 0 2px color-mix(in oklch, var(--accent) 20%, transparent)'
                }}
                onMouseLeave={(e) => {
                  const el = e.currentTarget
                  el.style.borderColor = 'var(--border)'
                  el.style.boxShadow = 'none'
                }}
              >
                <div style={{ color: 'var(--accent)', display: 'flex' }}>{gt.icon}</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>
                    {gt.label}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                    {gt.description}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const typeConfig = GOAL_TYPES.find((g) => g.type === selectedType)

  return (
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
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxWidth: '100%',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderTop: '2px solid var(--accent)',
          borderRadius: 14,
          boxShadow: '0 24px 64px -12px rgba(0,0,0,0.45)',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '88vh',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '18px 22px 14px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
              {typeConfig?.label ?? 'New goal'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              {typeConfig?.description}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => setSelectedType(null)}
              style={{
                padding: '4px 10px',
                border: '1px solid var(--border)',
                background: 'transparent',
                borderRadius: 6,
                color: 'var(--fg-muted)',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              Back
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                width: 26,
                height: 26,
                border: '1px solid var(--border)',
                background: 'transparent',
                borderRadius: 6,
                color: 'var(--fg-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
              }}
            >
              <X size={13} />
            </button>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{
            padding: '16px 22px',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            overflowY: 'auto',
          }}
        >
          <div>
            <label style={labelStyle()}>Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Vacation fund"
              required
              style={inputStyle()}
            />
          </div>

          {needsTargetAmount(selectedType) && (
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <label style={labelStyle()}>Target amount</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={targetAmount}
                  onChange={(e) => setTargetAmount(e.target.value)}
                  placeholder="0.00"
                  style={inputStyle()}
                />
              </div>
              <div style={{ width: 90 }}>
                <label style={labelStyle()}>Currency</label>
                <input
                  type="text"
                  maxLength={3}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  placeholder="USD"
                  style={inputStyle()}
                />
              </div>
            </div>
          )}

          {needsMinBalance(selectedType) && (
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <label style={labelStyle()}>Minimum balance threshold</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={minBalanceThreshold}
                  onChange={(e) => setMinBalanceThreshold(e.target.value)}
                  placeholder="0.00"
                  style={inputStyle()}
                />
              </div>
              <div style={{ width: 90 }}>
                <label style={labelStyle()}>Currency</label>
                <input
                  type="text"
                  maxLength={3}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  placeholder="USD"
                  style={inputStyle()}
                />
              </div>
            </div>
          )}

          {needsDebtPlan(selectedType) && (
            <div>
              <label style={labelStyle()}>Linked debt plan</label>
              <select
                value={linkedDebtPlanId}
                onChange={(e) => setLinkedDebtPlanId(e.target.value)}
                style={{ ...inputStyle(), cursor: 'pointer' }}
              >
                <option value="">None</option>
                {debtPlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name ?? p.method}
                  </option>
                ))}
              </select>
            </div>
          )}

          {needsCategory(selectedType) && (
            <div>
              <label style={labelStyle()}>Category</label>
              <CategorySelect
                categories={categories}
                value={linkedCategoryId}
                onChange={(id) => setLinkedCategoryId(id)}
                placeholder="Select category..."
              />
            </div>
          )}

          <div>
            <label style={labelStyle()}>
              Target date{targetDateRequired(selectedType) ? ' *' : ' (optional)'}
            </label>
            <input
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              required={targetDateRequired(selectedType)}
              style={inputStyle()}
            />
          </div>

          {members.length > 1 && (
            <div>
              <label style={labelStyle()}>Owner (optional)</label>
              <select
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
                style={{ ...inputStyle(), cursor: 'pointer' }}
              >
                <option value="">Shared</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label style={labelStyle()}>When goal is reached</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {COMPLETION_POLICIES.map((policy) => (
                <label
                  key={policy.value}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 8,
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: `1px solid ${completionPolicy === policy.value ? 'var(--accent)' : 'var(--border)'}`,
                    background:
                      completionPolicy === policy.value
                        ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                        : 'transparent',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="radio"
                    name="completionPolicy"
                    value={policy.value}
                    checked={completionPolicy === policy.value}
                    onChange={(e) => setCompletionPolicy(e.target.value)}
                    style={{ marginTop: 2, flexShrink: 0, accentColor: 'var(--accent)' }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                      {policy.label}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 1 }}>
                      {policy.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
              paddingTop: 4,
              paddingBottom: 6,
            }}
          >
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 14px',
                fontSize: 13,
                fontWeight: 500,
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
              type="submit"
              disabled={isPending}
              style={{
                padding: '8px 14px',
                fontSize: 13,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                cursor: isPending ? 'not-allowed' : 'pointer',
                opacity: isPending ? 0.7 : 1,
              }}
            >
              {isPending ? 'Creating...' : 'Create goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
