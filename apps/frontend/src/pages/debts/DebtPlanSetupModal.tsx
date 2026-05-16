import { useState } from 'react'
import { X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCreatePlanApiV1HouseholdsHouseholdIdDebtPlansPost,
  useComputeScheduleApiV1HouseholdsHouseholdIdDebtPlansPlanIdComputePost,
} from '@/api/generated/default/default'
import { DebtPlanMethod } from '@/api/generated/model/debtPlanMethod'
import type { AccountOut } from '@/api/generated/model/accountOut'

const METHOD_OPTIONS: { value: string; label: string; description: string }[] = [
  {
    value: DebtPlanMethod.avalanche,
    label: 'Avalanche',
    description: 'Highest APR first — least interest paid',
  },
  {
    value: DebtPlanMethod.snowball,
    label: 'Snowball',
    description: 'Smallest balance first — fastest wins',
  },
  {
    value: DebtPlanMethod.custom,
    label: 'Custom',
    description: 'You define the order',
  },
  {
    value: DebtPlanMethod.none,
    label: 'Track only',
    description: 'Track only, no plan',
  },
]

interface Props {
  householdId: string
  liabilityAccounts: AccountOut[]
  onClose: () => void
  onCreated: (planId: string) => void
}

export function DebtPlanSetupModal({ householdId, liabilityAccounts, onClose, onCreated }: Props) {
  const qc = useQueryClient()
  const [method, setMethod] = useState<string>(DebtPlanMethod.avalanche)
  const [extraPayment, setExtraPayment] = useState('')
  const [snowballFlow, setSnowballFlow] = useState(true)
  const [customOrder, setCustomOrder] = useState<string[]>(liabilityAccounts.map((a) => a.id))
  const [error, setError] = useState<string | null>(null)

  const createPlan = useCreatePlanApiV1HouseholdsHouseholdIdDebtPlansPost({
    mutation: {
      onError: () => setError('Failed to create debt plan'),
    },
  })

  const computeSchedule = useComputeScheduleApiV1HouseholdsHouseholdIdDebtPlansPlanIdComputePost({
    mutation: {
      onError: () => {},
    },
  })

  const isPending = createPlan.isPending || computeSchedule.isPending

  async function handleCreate() {
    setError(null)
    const today = new Date().toISOString().split('T')[0] ?? ''
    let planId: string
    try {
      const result = await createPlan.mutateAsync({
        householdId,
        data: {
          name: 'Debt Plan',
          method: method as (typeof DebtPlanMethod)[keyof typeof DebtPlanMethod],
          monthly_extra_payment: extraPayment || '0',
          currency: 'USD',
          snowball_flow: snowballFlow,
          account_ids: customOrder,
          effective_from: today,
        },
      })
      planId = result.id
    } catch {
      return
    }

    try {
      await computeSchedule.mutateAsync({ householdId, planId })
    } catch {
      // compute failed but plan was created
    }

    void qc.invalidateQueries()
    onCreated(planId)
  }

  function moveAccount(id: string, dir: -1 | 1) {
    setCustomOrder((prev) => {
      const idx = prev.indexOf(id)
      if (idx < 0) return prev
      const newIdx = idx + dir
      if (newIdx < 0 || newIdx >= prev.length) return prev
      const next = [...prev]
      ;[next[idx], next[newIdx]] = [next[newIdx] ?? '', next[idx] ?? '']
      return next
    })
  }

  const showSnowball = method === DebtPlanMethod.avalanche || method === DebtPlanMethod.snowball
  const showCustomOrder = method === DebtPlanMethod.custom

  const acctById = new Map(liabilityAccounts.map((a) => [a.id, a]))

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
          width: 480,
          maxWidth: '95vw',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: 'var(--shadow)',
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
            Create debt plan
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--fg-muted)',
              cursor: 'pointer',
              padding: 4,
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Method */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Payoff method
            </label>
            {METHOD_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: `1px solid ${method === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                  background:
                    method === opt.value
                      ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                      : 'transparent',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <input
                  type="radio"
                  name="debt-method"
                  value={opt.value}
                  checked={method === opt.value}
                  onChange={() => setMethod(opt.value)}
                  style={{ marginTop: 2, flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                    {opt.label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{opt.description}</div>
                </div>
              </label>
            ))}
          </div>

          {/* Extra payment */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Monthly extra payment (USD, optional)
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={extraPayment}
              onChange={(e) => setExtraPayment(e.target.value)}
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

          {/* Snowball flow */}
          {showSnowball && (
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 8,
                border: `1px solid ${snowballFlow ? 'var(--accent)' : 'var(--border)'}`,
                background: snowballFlow
                  ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                  : 'transparent',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                checked={snowballFlow}
                onChange={(e) => setSnowballFlow(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                  Snowball flow
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                  Redirect paid-off minimums to next debt
                </div>
              </div>
            </label>
          )}

          {/* Custom order */}
          {showCustomOrder && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                Payoff order (first to last)
              </label>
              {customOrder.map((id, i) => {
                const acct = acctById.get(id)
                if (!acct) return null
                return (
                  <div
                    key={id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 12px',
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                    }}
                  >
                    <span style={{ fontSize: 12, color: 'var(--fg-muted)', width: 20 }}>
                      {i + 1}.
                    </span>
                    <span style={{ flex: 1, fontSize: 13, color: 'var(--fg-primary)' }}>
                      {acct.name}
                    </span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        type="button"
                        onClick={() => moveAccount(id, -1)}
                        disabled={i === 0}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--fg-muted)',
                          cursor: i === 0 ? 'not-allowed' : 'pointer',
                          opacity: i === 0 ? 0.4 : 1,
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => moveAccount(id, 1)}
                        disabled={i === customOrder.length - 1}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--fg-muted)',
                          cursor: i === customOrder.length - 1 ? 'not-allowed' : 'pointer',
                          opacity: i === customOrder.length - 1 ? 0.4 : 1,
                        }}
                      >
                        ↓
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}
        </div>

        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 8,
            justifyContent: 'flex-end',
          }}
        >
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
            disabled={isPending}
            onClick={() => void handleCreate()}
            style={{
              padding: '7px 18px',
              fontSize: 13,
              fontWeight: 500,
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 8,
              color: 'var(--accent-fg)',
              cursor: isPending ? 'not-allowed' : 'pointer',
              opacity: isPending ? 0.7 : 1,
            }}
          >
            {isPending ? 'Creating...' : 'Create plan'}
          </button>
        </div>
      </div>
    </div>
  )
}
