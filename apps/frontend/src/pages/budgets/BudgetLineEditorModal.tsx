import { useState } from 'react'
import { X } from 'lucide-react'
import {
  useCreateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesPost,
  useUpdateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesLineIdPatch,
} from '@/api/generated/budgets/budgets'
import { useQueryClient } from '@tanstack/react-query'
import { CategorySelect } from '@/components/CategorySelect'
import { CurrencySelect } from '@/components/CurrencySelect'
import type { CategoryOut } from '@/api/generated/model/categoryOut'
import type { BudgetLineOut } from '@/api/generated/model/budgetLineOut'
import { RolloverPolicy } from '@/api/generated/model/rolloverPolicy'

const ROLLOVER_OPTIONS: { value: string; label: string; description: string }[] = [
  {
    value: RolloverPolicy.none,
    label: 'None',
    description: 'Unused funds disappear at period end',
  },
  {
    value: RolloverPolicy.accumulate,
    label: 'Accumulate',
    description: 'Unused funds roll to next period',
  },
  {
    value: RolloverPolicy.accumulate_capped,
    label: 'Accumulate (capped)',
    description: 'Rolls over up to a cap',
  },
  {
    value: RolloverPolicy.debt_carry,
    label: 'Debt carry',
    description: 'Overage carries as debt next period',
  },
  {
    value: RolloverPolicy.reset_on_overspend,
    label: 'Reset on overspend',
    description: 'Resets if you go over',
  },
]

interface Props {
  householdId: string
  budgetId: string
  categories: CategoryOut[]
  currency: string
  existingLine?: BudgetLineOut
  onClose: () => void
}

export function BudgetLineEditorModal({
  householdId,
  budgetId,
  categories,
  currency,
  existingLine,
  onClose,
}: Props) {
  const qc = useQueryClient()
  const [categoryId, setCategoryId] = useState<string | null>(existingLine?.category_id ?? null)
  const [amount, setAmount] = useState(existingLine?.planned_amount ?? '')
  const [rolloverPolicy, setRolloverPolicy] = useState<string>(
    existingLine?.rollover_policy ?? RolloverPolicy.none
  )
  const [rolloverCap, setRolloverCap] = useState(
    existingLine?.rollover_cap != null ? String(existingLine.rollover_cap) : ''
  )
  const [lineCurrency, setLineCurrency] = useState(existingLine?.currency ?? currency)
  const [error, setError] = useState<string | null>(null)

  const createLine = useCreateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries()
        onClose()
      },
      onError: () => setError('Failed to save budget line'),
    },
  })

  const updateLine = useUpdateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesLineIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries()
        onClose()
      },
      onError: () => setError('Failed to update budget line'),
    },
  })

  const isPending = createLine.isPending || updateLine.isPending

  function handleSubmit() {
    if (!categoryId) {
      setError('Select a category')
      return
    }
    const parsed = parseFloat(amount)
    if (isNaN(parsed) || parsed <= 0) {
      setError('Enter a valid amount')
      return
    }
    const capVal =
      rolloverPolicy === RolloverPolicy.accumulate_capped && rolloverCap ? rolloverCap : undefined

    if (existingLine) {
      updateLine.mutate({
        householdId,
        budgetId,
        lineId: existingLine.id,
        data: {
          planned_amount: amount,
          currency: lineCurrency,
          rollover_policy: rolloverPolicy as (typeof RolloverPolicy)[keyof typeof RolloverPolicy],
          rollover_cap: capVal ?? null,
        },
      })
    } else {
      createLine.mutate({
        householdId,
        budgetId,
        data: {
          category_id: categoryId,
          planned_amount: amount,
          currency: lineCurrency,
          rollover_policy: rolloverPolicy as (typeof RolloverPolicy)[keyof typeof RolloverPolicy],
          rollover_cap: capVal ?? null,
        },
      })
    }
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
          width: 440,
          maxWidth: '95vw',
          boxShadow: 'var(--shadow)',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
            {existingLine ? 'Edit budget line' : 'Add budget line'}
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Category
            </label>
            <CategorySelect
              categories={categories}
              value={categoryId}
              onChange={setCategoryId}
              disabled={!!existingLine}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Planned amount ({lineCurrency})
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
              Currency
            </label>
            <CurrencySelect value={lineCurrency} onChange={setLineCurrency} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Rollover policy
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {ROLLOVER_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: `1px solid ${rolloverPolicy === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                    background:
                      rolloverPolicy === opt.value
                        ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                        : 'transparent',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                >
                  <input
                    type="radio"
                    name="rollover"
                    value={opt.value}
                    checked={rolloverPolicy === opt.value}
                    onChange={() => setRolloverPolicy(opt.value)}
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
          </div>

          {rolloverPolicy === RolloverPolicy.accumulate_capped && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                Rollover cap ({lineCurrency})
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={rolloverCap}
                onChange={(e) => setRolloverCap(e.target.value)}
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
          )}
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
            disabled={isPending}
            onClick={handleSubmit}
            style={{
              padding: '7px 14px',
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
            {isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
