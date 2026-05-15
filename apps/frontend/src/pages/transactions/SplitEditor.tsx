import { useState } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useSetSplitsCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdSplitsPost,
  getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey,
} from '@/api/generated/transactions/transactions'
import type { TransactionDetailOut } from '@/api/generated/model/transactionDetailOut'
import type { SplitAllocationOut } from '@/api/generated/model/splitAllocationOut'
import type { CategoryOut } from '@/api/generated/model/categoryOut'
import type { MembershipOut } from '@/api/generated/model/membershipOut'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import { categoryColor } from '@/domain/transactions'
import { CategorySelect } from '@/components/CategorySelect'

type SplitRow = {
  id: string
  amount: string
  category_id: string | null
  attributed_to_user_id: string | null
  tag_ids: string[]
}

interface Props {
  householdId: string
  transaction: TransactionDetailOut
  categories: CategoryOut[]
  members: MembershipOut[]
  open: boolean
  onClose: () => void
}

export function SplitEditor({
  householdId,
  transaction,
  categories,
  members,
  open,
  onClose,
}: Props) {
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const qc = useQueryClient()

  const totalAmount = parseFloat(transaction.amount)
  const currency = transaction.currency

  function initRows(splits: SplitAllocationOut[] | undefined): SplitRow[] {
    if (!splits || splits.length === 0) {
      return [
        {
          id: crypto.randomUUID(),
          amount: transaction.amount,
          category_id: null,
          attributed_to_user_id: null,
          tag_ids: [],
        },
      ]
    }
    return splits.map((s) => ({
      id: s.id,
      amount: s.amount,
      category_id: s.category_id ?? null,
      attributed_to_user_id: s.attributed_to_user_id ?? null,
      tag_ids: (s.tag_ids ?? []).filter((t): t is string => typeof t === 'string'),
    }))
  }

  const [rows, setRows] = useState<SplitRow[]>(() => initRows(transaction.splits))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { mutateAsync: setSplits } =
    useSetSplitsCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdSplitsPost()

  const splitTotal = rows.reduce((s, r) => s + parseFloat(r.amount || '0'), 0)
  const remaining = totalAmount - splitTotal
  const isBalanced = Math.abs(remaining) < 0.01

  function updateRow(id: string, patch: Partial<SplitRow>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function addRow() {
    setRows((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        amount: remaining > 0 ? remaining.toFixed(2) : '0.00',
        category_id: null,
        attributed_to_user_id: null,
        tag_ids: [],
      },
    ])
  }

  function removeRow(id: string) {
    if (rows.length <= 1) return
    setRows((prev) => prev.filter((r) => r.id !== id))
  }

  async function handleSave() {
    if (!isBalanced) {
      setError('Split amounts must equal the transaction total.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await setSplits({
        householdId,
        transactionId: transaction.id,
        data: {
          splits: rows.map((r) => ({
            amount: r.amount,
            currency,
            category_id: r.category_id ?? undefined,
            attributed_to_user_id: r.attributed_to_user_id ?? undefined,
            tag_ids: r.tag_ids,
            manually_categorized: r.category_id != null,
          })),
        },
      })
      await qc.invalidateQueries({
        queryKey:
          getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey(
            householdId,
            transaction.id
          ),
      })
      onClose()
    } catch {
      setError('Failed to save splits. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 300 }}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 301,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          width: 580,
          maxWidth: 'calc(100vw - 32px)',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '20px 24px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
              Edit splits
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              Total:{' '}
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
                {fmt(totalAmount, privacyMode, currency)}
              </span>
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

        {/* Rows */}
        <div
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: '16px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          {rows.map((row, i) => (
            <SplitRowEditor
              key={row.id}
              row={row}
              index={i}
              categories={categories}
              members={members}
              currency={currency}
              canRemove={rows.length > 1}
              onChange={(patch) => updateRow(row.id, patch)}
              onRemove={() => removeRow(row.id)}
            />
          ))}

          <button
            type="button"
            onClick={addRow}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px dashed var(--border)',
              background: 'none',
              color: 'var(--fg-muted)',
              fontSize: 12,
              cursor: 'pointer',
              alignSelf: 'flex-start',
            }}
          >
            <Plus size={12} /> Add split
          </button>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border)',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 12,
            }}
          >
            <span style={{ color: 'var(--fg-muted)' }}>Unallocated</span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                color: isBalanced
                  ? 'var(--success)'
                  : Math.abs(remaining) < 0.005
                    ? 'var(--success)'
                    : 'var(--danger)',
              }}
            >
              {fmt(remaining, privacyMode, currency)}
            </span>
          </div>

          {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1,
                padding: '9px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'none',
                color: 'var(--fg-secondary)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!isBalanced || saving}
              onClick={() => void handleSave()}
              style={{
                flex: 1,
                padding: '9px',
                borderRadius: 8,
                border: 'none',
                background: isBalanced ? 'var(--accent)' : 'var(--border)',
                color: isBalanced ? 'var(--accent-fg)' : 'var(--fg-muted)',
                fontSize: 13,
                fontWeight: 500,
                cursor: isBalanced && !saving ? 'pointer' : 'not-allowed',
              }}
            >
              {saving ? 'Saving...' : 'Save splits'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

function SplitRowEditor({
  row,
  index,
  categories,
  members,
  currency,
  canRemove,
  onChange,
  onRemove,
}: {
  row: SplitRow
  index: number
  categories: CategoryOut[]
  members: MembershipOut[]
  currency: string
  canRemove: boolean
  onChange: (patch: Partial<SplitRow>) => void
  onRemove: () => void
}) {
  const cat = categories.find((c) => c.id === row.category_id)

  return (
    <div
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase' as const,
            letterSpacing: '0.05em',
          }}
        >
          Split {index + 1}
          {cat && (
            <span style={{ marginLeft: 6 }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: categoryColor(cat.color, cat.name),
                  marginRight: 4,
                  verticalAlign: 'middle',
                }}
              />
              {cat.name}
            </span>
          )}
        </div>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--fg-muted)',
              cursor: 'pointer',
              padding: 2,
            }}
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Amount ({currency})</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={row.amount}
            onChange={(e) => onChange({ amount: e.target.value })}
            style={{
              padding: '7px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: 'var(--fg-primary)',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
              outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Category</label>
          <CategorySelect
            categories={categories}
            value={row.category_id}
            onChange={(id) => onChange({ category_id: id })}
            placeholder="None"
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Attributed to</label>
          <select
            value={row.attributed_to_user_id ?? ''}
            onChange={(e) => onChange({ attributed_to_user_id: e.target.value || null })}
            style={{
              padding: '7px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: row.attributed_to_user_id ? 'var(--fg-primary)' : 'var(--fg-muted)',
              fontSize: 13,
              outline: 'none',
            }}
          >
            <option value="">Anyone</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.user.display_name}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}
