import { useState } from 'react'
import { X, ChevronLeft } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCreateBudgetApiV1HouseholdsHouseholdIdBudgetsPost,
  useCreateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesPost,
} from '@/api/generated/budgets/budgets'
import { useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet } from '@/api/generated/classification/classification'
import { BudgetPeriod } from '@/api/generated/model/budgetPeriod'
import { BudgetMethod } from '@/api/generated/model/budgetMethod'
import { ExpectedIncomeStrategy } from '@/api/generated/model/expectedIncomeStrategy'
import { RolloverPolicy } from '@/api/generated/model/rolloverPolicy'
import { CategorySelect } from '@/components/CategorySelect'

const PERIOD_OPTIONS: { value: string; label: string }[] = [
  { value: BudgetPeriod.monthly, label: 'Monthly' },
  { value: BudgetPeriod.weekly, label: 'Weekly' },
  { value: BudgetPeriod.biweekly, label: 'Biweekly' },
  { value: BudgetPeriod.semimonthly, label: 'Semimonthly' },
  { value: BudgetPeriod.annual, label: 'Annual' },
]

const METHOD_OPTIONS: { value: string; label: string; description: string }[] = [
  {
    value: BudgetMethod.zero_based,
    label: 'Zero-Based',
    description: 'Every dollar has a job',
  },
  {
    value: BudgetMethod.envelope,
    label: 'Envelope',
    description: 'Spend until the envelope is empty',
  },
  {
    value: BudgetMethod.fifty_thirty_twenty,
    label: '50/30/20',
    description: '50% needs, 30% wants, 20% savings — automatic',
  },
  {
    value: BudgetMethod.rolling_average,
    label: 'Rolling Average',
    description: 'Auto-sets from your history',
  },
  {
    value: BudgetMethod.manual,
    label: 'Manual',
    description: "You're in full control",
  },
]

const INCOME_STRATEGY_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: ExpectedIncomeStrategy.fixed, label: 'Fixed', description: 'Same amount every period' },
  {
    value: ExpectedIncomeStrategy.from_income_sources,
    label: 'From income sources',
    description: 'Sum of declared income sources',
  },
  {
    value: ExpectedIncomeStrategy.last_period_actual,
    label: 'Last period actual',
    description: 'What actually came in last period',
  },
  {
    value: ExpectedIncomeStrategy.rolling_average,
    label: 'Rolling average',
    description: 'Average over last 3 periods',
  },
  {
    value: ExpectedIncomeStrategy.manual_per_period,
    label: 'Manual per period',
    description: 'You enter the amount each period',
  },
]

interface DraftLine {
  categoryId: string | null
  amount: string
}

interface Props {
  householdId: string
  onClose: () => void
  onCreated: (budgetId: string) => void
}

export function BudgetSetupWizard({ householdId, onClose, onCreated }: Props) {
  const qc = useQueryClient()
  const [step, setStep] = useState(1)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [period, setPeriod] = useState<string>(BudgetPeriod.monthly)
  const [method, setMethod] = useState<string>(BudgetMethod.zero_based)

  const [incomeStrategy, setIncomeStrategy] = useState<string>(ExpectedIncomeStrategy.fixed)
  const [incomeAmount, setIncomeAmount] = useState('')

  const [lines, setLines] = useState<DraftLine[]>([])

  const { data: categories = [] } = useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet(
    householdId,
    { query: { enabled: !!householdId } }
  )

  const createBudget = useCreateBudgetApiV1HouseholdsHouseholdIdBudgetsPost({
    mutation: {
      onError: () => setError('Failed to create budget'),
    },
  })

  const createLine = useCreateBudgetLineApiV1HouseholdsHouseholdIdBudgetsBudgetIdLinesPost({
    mutation: {
      onError: () => setError('Failed to add budget line'),
    },
  })

  async function handleCreate(skipLines = false) {
    setError(null)
    const today = new Date().toISOString().split('T')[0] ?? ''
    const expectedIncome =
      (incomeStrategy === ExpectedIncomeStrategy.fixed ||
        incomeStrategy === ExpectedIncomeStrategy.manual_per_period) &&
      incomeAmount
        ? incomeAmount
        : undefined

    let budgetId: string
    try {
      const result = await createBudget.mutateAsync({
        householdId,
        data: {
          name,
          period: period as (typeof BudgetPeriod)[keyof typeof BudgetPeriod],
          method: method as (typeof BudgetMethod)[keyof typeof BudgetMethod],
          start_date: today,
          expected_income_strategy:
            incomeStrategy as (typeof ExpectedIncomeStrategy)[keyof typeof ExpectedIncomeStrategy],
          expected_income: expectedIncome ?? null,
          currency: 'USD',
        },
      })
      budgetId = result.id
    } catch {
      return
    }

    if (!skipLines) {
      for (const line of lines) {
        if (!line.categoryId || !line.amount) continue
        try {
          await createLine.mutateAsync({
            householdId,
            budgetId,
            data: {
              category_id: line.categoryId,
              planned_amount: line.amount,
              currency: 'USD',
              rollover_policy: RolloverPolicy.none,
              rollover_cap: null,
            },
          })
        } catch {
          // continue with remaining lines
        }
      }
    }

    void qc.invalidateQueries()
    onCreated(budgetId)
  }

  function addLine() {
    setLines((prev) => [...prev, { categoryId: null, amount: '' }])
  }

  function updateLine(i: number, field: keyof DraftLine, value: string | null) {
    setLines((prev) =>
      prev.map((l, idx) =>
        idx === i ? { ...l, [field]: field === 'categoryId' ? value : (value ?? '') } : l
      )
    )
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i))
  }

  const isPending = createBudget.isPending || createLine.isPending

  const showIncomeAmount =
    incomeStrategy === ExpectedIncomeStrategy.fixed ||
    incomeStrategy === ExpectedIncomeStrategy.manual_per_period

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
          width: 500,
          maxWidth: '95vw',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => s - 1)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--fg-muted)',
                  cursor: 'pointer',
                  padding: 2,
                }}
              >
                <ChevronLeft size={16} />
              </button>
            )}
            <div>
              <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
                {step === 1 && 'New budget'}
                {step === 2 && 'Expected income'}
                {step === 3 && 'Budget lines'}
              </h2>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Step {step} of 3</div>
            </div>
          </div>
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

        {/* Step indicator */}
        <div
          style={{
            display: 'flex',
            gap: 0,
            padding: '0 20px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              style={{
                flex: 1,
                height: 3,
                background: s <= step ? 'var(--accent)' : 'var(--border)',
                transition: 'background 0.2s',
              }}
            />
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                  Budget name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Household Budget"
                  style={{
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-elevated)',
                    color: 'var(--fg-primary)',
                    fontSize: 13,
                    outline: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                  Period
                </label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {PERIOD_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setPeriod(opt.value)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: 8,
                        border: `1px solid ${period === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                        background:
                          period === opt.value
                            ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                            : 'transparent',
                        color: period === opt.value ? 'var(--accent)' : 'var(--fg-secondary)',
                        fontSize: 13,
                        fontWeight: period === opt.value ? 500 : 400,
                        cursor: 'pointer',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                  Method
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
                      name="method"
                      value={opt.value}
                      checked={method === opt.value}
                      onChange={() => setMethod(opt.value)}
                      style={{ marginTop: 2, flexShrink: 0 }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                        {opt.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                        {opt.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {INCOME_STRATEGY_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: `1px solid ${incomeStrategy === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                      background:
                        incomeStrategy === opt.value
                          ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                          : 'transparent',
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                  >
                    <input
                      type="radio"
                      name="income-strategy"
                      value={opt.value}
                      checked={incomeStrategy === opt.value}
                      onChange={() => setIncomeStrategy(opt.value)}
                      style={{ marginTop: 2, flexShrink: 0 }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                        {opt.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                        {opt.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>

              {showIncomeAmount && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                    Expected income (USD)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={incomeAmount}
                    onChange={(e) => setIncomeAmount(e.target.value)}
                    placeholder="0.00"
                    style={{
                      padding: '8px 10px',
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
          )}

          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
                Add budget lines to allocate spending. You can always add more later.
              </div>

              {lines.map((line, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    gap: 8,
                    alignItems: 'center',
                    padding: '10px 12px',
                    background: 'var(--bg-secondary)',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <CategorySelect
                      categories={categories}
                      value={line.categoryId}
                      onChange={(id) => updateLine(i, 'categoryId', id)}
                    />
                  </div>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.amount}
                    onChange={(e) => updateLine(i, 'amount', e.target.value)}
                    placeholder="Amount"
                    style={{
                      width: 100,
                      padding: '7px 8px',
                      borderRadius: 8,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-elevated)',
                      color: 'var(--fg-primary)',
                      fontSize: 13,
                      fontFamily: "'Geist Mono', monospace",
                      outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => removeLine(i)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--fg-muted)',
                      cursor: 'pointer',
                      padding: 4,
                      fontSize: 16,
                      lineHeight: 1,
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}

              <button
                type="button"
                onClick={addLine}
                style={{
                  padding: '8px 14px',
                  background: 'none',
                  border: '1px dashed var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-muted)',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                + Add line
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 8,
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          {error && (
            <div style={{ fontSize: 12, color: 'var(--danger)', alignSelf: 'center' }}>{error}</div>
          )}
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            {step === 3 && (
              <button
                type="button"
                disabled={isPending}
                onClick={() => void handleCreate(true)}
                style={{
                  padding: '7px 14px',
                  fontSize: 13,
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-secondary)',
                  cursor: isPending ? 'not-allowed' : 'pointer',
                }}
              >
                Skip for now
              </button>
            )}
            <button
              type="button"
              disabled={step === 1 && !name.trim()}
              onClick={() => {
                if (step < 3) {
                  setStep((s) => s + 1)
                } else {
                  void handleCreate(false)
                }
              }}
              style={{
                padding: '7px 18px',
                fontSize: 13,
                fontWeight: 500,
                background: 'var(--accent)',
                border: 'none',
                borderRadius: 8,
                color: 'var(--accent-fg)',
                cursor: isPending || (step === 1 && !name.trim()) ? 'not-allowed' : 'pointer',
                opacity: isPending || (step === 1 && !name.trim()) ? 0.6 : 1,
              }}
            >
              {isPending ? 'Creating...' : step < 3 ? 'Continue' : 'Create budget'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
