import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Plus, RefreshCw, ChevronDown } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetBudgetApiV1HouseholdsHouseholdIdBudgetsBudgetIdGet,
  useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet,
  useComputeActualsApiV1HouseholdsHouseholdIdBudgetsBudgetIdComputePost,
  useListBudgetHistoryApiV1HouseholdsHouseholdIdBudgetsBudgetIdHistoryGet,
} from '@/api/generated/budgets/budgets'
import { useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet } from '@/api/generated/classification/classification'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { categoryColor } from '@/domain/transactions'
import type { BudgetLineStatusOut } from '@/api/generated/model/budgetLineStatusOut'
import { BudgetLineEditorModal } from './BudgetLineEditorModal'
import { BudgetMethod } from '@/api/generated/model/budgetMethod'

function progressColor(pct: number): string {
  if (pct >= 100) return 'var(--danger)'
  if (pct >= 80) return 'var(--warning)'
  return 'var(--success)'
}

function formatPeriodDate(dateStr: string): string {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  const date = new Date(y, m - 1, d)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
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

function BudgetLineRow({
  lineStatus,
  categoryName,
  categoryColorVal,
  currency,
  onEdit,
}: {
  lineStatus: BudgetLineStatusOut
  categoryName: string
  categoryColorVal: string
  currency: string
  onEdit: () => void
}) {
  const spent = parseFloat(lineStatus.actual)
  const planned = parseFloat(lineStatus.planned)
  const carriedIn = parseFloat(lineStatus.carried_in)
  const remaining = parseFloat(lineStatus.remaining)
  const pct = planned > 0 ? Math.min(100, Math.round((spent / planned) * 100)) : 0
  const over = spent > planned

  return (
    <div
      onClick={onEdit}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 0',
        borderBottom: '1px solid var(--border)',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.background =
          'color-mix(in oklch, var(--fg-primary) 3%, transparent)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.background = 'transparent'
      }}
    >
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: categoryColorVal,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: 13,
              color: 'var(--fg-secondary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {categoryName}
          </span>
          {carriedIn > 0 && (
            <span
              style={{
                fontSize: 11,
                color: 'var(--info)',
                background: 'color-mix(in oklch, var(--info) 12%, transparent)',
                padding: '1px 6px',
                borderRadius: 4,
                flexShrink: 0,
              }}
            >
              {'↩'} {formatAmount(carriedIn, { currency })} carried in
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 6,
            flexShrink: 0,
            fontFamily: "'Geist Mono', monospace",
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            {formatAmount(spent, { currency })}
          </span>
          <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            / {formatAmount(planned, { currency })}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            flex: 1,
            height: 6,
            borderRadius: 99,
            background: 'var(--border)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${Math.min(100, pct)}%`,
              borderRadius: 99,
              background: progressColor(pct),
              transition: 'width 0.4s ease',
            }}
          />
        </div>
        <span
          style={{
            fontSize: 12,
            fontFamily: "'Geist Mono', monospace",
            color: over ? 'var(--danger)' : 'var(--fg-muted)',
            minWidth: 60,
            textAlign: 'right' as const,
          }}
        >
          {over
            ? `${formatAmount(Math.abs(remaining), { currency })} over`
            : `${formatAmount(remaining, { currency })} left`}
        </span>
      </div>
    </div>
  )
}

function ZeroBasedPanel({
  totalPlanned,
  expectedIncome,
  currency,
}: {
  totalPlanned: number
  expectedIncome: number
  currency: string
}) {
  const unallocated = expectedIncome - totalPlanned
  const isOver = unallocated < 0
  return (
    <div
      style={{
        padding: '14px 16px',
        borderRadius: 8,
        background: isOver
          ? 'color-mix(in oklch, var(--danger) 10%, transparent)'
          : 'color-mix(in oklch, var(--success) 10%, transparent)',
        border: `1px solid ${isOver ? 'color-mix(in oklch, var(--danger) 30%, transparent)' : 'color-mix(in oklch, var(--success) 30%, transparent)'}`,
      }}
    >
      <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>
        {isOver ? 'Over-allocated' : 'Unallocated'}
      </div>
      <div
        style={{
          fontSize: 20,
          fontWeight: 700,
          fontFamily: "'Geist Mono', monospace",
          color: isOver ? 'var(--danger)' : 'var(--success)',
          letterSpacing: '-0.02em',
        }}
      >
        {formatAmount(Math.abs(unallocated), { currency })}
      </div>
    </div>
  )
}

function FiftyThirtyTwentyPanel({
  lines,
  categories,
  currency,
}: {
  lines: BudgetLineStatusOut[]
  categories: { id: string; budget_role?: string | null }[]
  currency: string
}) {
  const catById = new Map(categories.map((c) => [c.id, c]))

  let needs = 0,
    wants = 0,
    savings = 0
  for (const l of lines) {
    const cat = catById.get(l.line.category_id)
    const role = (cat as Record<string, unknown> | undefined)?.['budget_role'] as string | undefined
    const amt = parseFloat(l.actual)
    if (role === 'savings') savings += amt
    else if (role === 'wants') wants += amt
    else needs += amt
  }
  const total = needs + wants + savings || 1

  function Bar50({
    label,
    actual,
    pct,
    target,
  }: {
    label: string
    actual: number
    pct: number
    target: number
  }) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: 'var(--fg-secondary)', fontWeight: 500 }}>{label}</span>
          <span style={{ fontFamily: "'Geist Mono', monospace", color: 'var(--fg-muted)' }}>
            {Math.round(pct)}%{' '}
            <span style={{ color: 'var(--fg-muted)', fontWeight: 400 }}>/ {target}% target</span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              flex: 1,
              height: 6,
              borderRadius: 99,
              background: 'var(--border)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, pct)}%`,
                borderRadius: 99,
                background: pct > target ? 'var(--warning)' : 'var(--accent)',
                transition: 'width 0.4s',
              }}
            />
          </div>
          <span
            style={{
              fontSize: 12,
              color: 'var(--fg-muted)',
              fontFamily: "'Geist Mono', monospace",
              minWidth: 60,
              textAlign: 'right' as const,
            }}
          >
            {formatAmount(actual, { currency })}
          </span>
        </div>
      </div>
    )
  }

  const needsPct = (needs / total) * 100
  const wantsPct = (wants / total) * 100
  const savingsPct = (savings / total) * 100

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '14px 16px',
        background: 'var(--bg-secondary)',
        borderRadius: 8,
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-secondary)' }}>
        50/30/20 breakdown
      </div>
      <Bar50 label="Needs" actual={needs} pct={needsPct} target={50} />
      <Bar50 label="Wants" actual={wants} pct={wantsPct} target={30} />
      <Bar50 label="Savings" actual={savings} pct={savingsPct} target={20} />
    </div>
  )
}

export function BudgetDetailPage() {
  const { budgetId } = useParams<{ budgetId: string }>()
  const navigate = useNavigate()
  const { householdId } = useHousehold()
  const qc = useQueryClient()

  const [asOf, setAsOf] = useState<string | undefined>(undefined)
  const [showLineEditor, setShowLineEditor] = useState(false)
  const [editingLine, setEditingLine] = useState<BudgetLineStatusOut | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const hid = householdId ?? ''
  const bid = budgetId ?? ''

  const { data: budget } = useGetBudgetApiV1HouseholdsHouseholdIdBudgetsBudgetIdGet(hid, bid, {
    query: { enabled: !!hid && !!bid },
  })

  const { data: status, isLoading: statusLoading } =
    useGetBudgetStatusApiV1HouseholdsHouseholdIdBudgetsBudgetIdStatusGet(
      hid,
      bid,
      asOf ? { as_of: asOf } : {},
      { query: { enabled: !!hid && !!bid } }
    )

  const { data: categories = [] } = useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet(hid, {
    query: { enabled: !!hid },
  })

  const { data: history = [] } =
    useListBudgetHistoryApiV1HouseholdsHouseholdIdBudgetsBudgetIdHistoryGet(hid, bid, {
      query: { enabled: !!hid && !!bid && showHistory },
    })

  const computeActuals = useComputeActualsApiV1HouseholdsHouseholdIdBudgetsBudgetIdComputePost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries()
        showToastMsg('Actuals computed')
      },
      onError: () => showToastMsg('Compute failed'),
    },
  })

  function showToastMsg(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  function stepPeriod(dir: -1 | 1) {
    const base = asOf ?? status?.period_start
    if (!base) return
    const parts = base.split('-')
    const y = parseInt(parts[0] ?? '2000', 10)
    const m = parseInt(parts[1] ?? '1', 10)
    const newDate = new Date(y, m - 1 + dir, 1)
    setAsOf(`${newDate.getFullYear()}-${String(newDate.getMonth() + 1).padStart(2, '0')}-01`)
  }

  const catById = new Map(categories.map((c) => [c.id, c]))
  const expectedIncome = status?.expected_income != null ? parseFloat(status.expected_income) : null
  const totalSpent = status ? status.lines.reduce((s, l) => s + parseFloat(l.actual), 0) : 0
  const totalPlanned = status ? status.lines.reduce((s, l) => s + parseFloat(l.planned), 0) : 0

  if (!householdId || !budgetId) {
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
          onClick={() => navigate('/budget')}
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
          <ChevronLeft size={14} /> Budgets
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
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
              {budget?.name ?? '…'}
            </h1>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {budget && (
                <>
                  <Badge label={budget.period} color="var(--accent)" />
                  <Badge label={methodLabel(budget.method)} />
                  {expectedIncome != null && (
                    <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                      {formatAmount(expectedIncome, { currency: budget.currency })} expected income
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <button
              type="button"
              disabled={computeActuals.isPending}
              onClick={() => computeActuals.mutate({ householdId: hid, budgetId: bid })}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 12px',
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 8,
                color: 'var(--fg-secondary)',
                fontSize: 13,
                cursor: computeActuals.isPending ? 'not-allowed' : 'pointer',
                opacity: computeActuals.isPending ? 0.6 : 1,
              }}
            >
              <RefreshCw size={13} />
              Compute actuals
            </button>
            <button
              type="button"
              onClick={() => {
                setEditingLine(null)
                setShowLineEditor(true)
              }}
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
              <Plus size={14} /> Add line
            </button>
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
        {/* Period selector */}
        {status && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <button
              type="button"
              onClick={() => stepPeriod(-1)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--fg-secondary)',
                cursor: 'pointer',
                padding: '4px 8px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ChevronLeft size={14} />
            </button>
            <span style={{ fontSize: 13, color: 'var(--fg-secondary)', fontWeight: 500 }}>
              {formatPeriodDate(status.period_start)} – {formatPeriodDate(status.period_end)}
            </span>
            <button
              type="button"
              onClick={() => stepPeriod(1)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--fg-secondary)',
                cursor: 'pointer',
                padding: '4px 8px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ChevronRight size={14} />
            </button>
            {asOf && (
              <button
                type="button"
                onClick={() => setAsOf(undefined)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--accent)',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                Back to current
              </button>
            )}
          </div>
        )}

        {/* Income section */}
        {expectedIncome != null && budget && (
          <div
            style={{
              display: 'flex',
              gap: 16,
              padding: '14px 16px',
              background: 'var(--bg-secondary)',
              borderRadius: 10,
              border: '1px solid var(--border)',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 4,
                }}
              >
                Expected income
              </div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 600,
                  fontFamily: "'Geist Mono', monospace",
                  color: 'var(--fg-primary)',
                }}
              >
                {formatAmount(expectedIncome, { currency: budget.currency })}
              </div>
            </div>
            {status && (
              <div style={{ borderLeft: '1px solid var(--border)', paddingLeft: 16 }}>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--fg-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 4,
                  }}
                >
                  Actual income
                </div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    fontFamily: "'Geist Mono', monospace",
                    color: 'var(--success)',
                  }}
                >
                  {formatAmount(totalSpent, { currency: budget.currency })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Method-specific panel */}
        {budget && status && (
          <>
            {budget.method === BudgetMethod.zero_based && expectedIncome != null && (
              <ZeroBasedPanel
                totalPlanned={totalPlanned}
                expectedIncome={expectedIncome}
                currency={budget.currency}
              />
            )}
            {budget.method === BudgetMethod.fifty_thirty_twenty && (
              <FiftyThirtyTwentyPanel
                lines={status.lines}
                categories={categories}
                currency={budget.currency}
              />
            )}
          </>
        )}

        {/* Budget lines */}
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
              marginBottom: 4,
            }}
          >
            Budget lines
          </div>

          {statusLoading ? (
            <div style={{ color: 'var(--fg-muted)', fontSize: 13, padding: '16px 0' }}>
              Loading...
            </div>
          ) : !status || status.lines.length === 0 ? (
            <div style={{ color: 'var(--fg-muted)', fontSize: 13, padding: '16px 0' }}>
              No budget lines yet. Add a line to start allocating.
            </div>
          ) : (
            status.lines.map((lineStatus) => {
              const cat = catById.get(lineStatus.line.category_id)
              const name = cat?.name ?? 'Unknown'
              const color = cat ? categoryColor(cat.color, cat.name) : 'var(--fg-muted)'
              return (
                <BudgetLineRow
                  key={lineStatus.line.id}
                  lineStatus={lineStatus}
                  categoryName={name}
                  categoryColorVal={color}
                  currency={budget?.currency ?? 'USD'}
                  onEdit={() => {
                    setEditingLine(lineStatus)
                    setShowLineEditor(true)
                  }}
                />
              )
            })
          )}
        </div>

        {/* Version history */}
        <div
          style={{
            border: '1px solid var(--border)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          <button
            type="button"
            onClick={() => setShowHistory((s) => !s)}
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
            Version history
            <ChevronDown
              size={14}
              style={{
                transform: showHistory ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.2s',
              }}
            />
          </button>
          {showHistory && (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              {history.length === 0 ? (
                <div style={{ padding: '12px 18px', fontSize: 13, color: 'var(--fg-muted)' }}>
                  No version history
                </div>
              ) : (
                history.map((v) => (
                  <div
                    key={v.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '10px 18px',
                      borderBottom: '1px solid var(--border)',
                      fontSize: 13,
                    }}
                  >
                    <span style={{ color: 'var(--fg-primary)' }}>{v.name}</span>
                    <span
                      style={{
                        color: 'var(--fg-muted)',
                        fontFamily: "'Geist Mono', monospace",
                        fontSize: 12,
                      }}
                    >
                      {formatPeriodDate(v.effective_from)}
                      {v.effective_to ? ` – ${formatPeriodDate(v.effective_to)}` : ' – present'}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Line editor modal */}
      {showLineEditor && budget && (
        <BudgetLineEditorModal
          householdId={hid}
          budgetId={bid}
          categories={categories}
          currency={budget.currency}
          existingLine={editingLine?.line}
          onClose={() => {
            setShowLineEditor(false)
            setEditingLine(null)
          }}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            background: 'var(--fg-primary)',
            color: 'var(--bg-primary)',
            padding: '10px 16px',
            borderRadius: 8,
            fontSize: 13,
            zIndex: 300,
            boxShadow: 'var(--shadow)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
