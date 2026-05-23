import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet,
  usePairTransferCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdTransferPairPost,
  getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey,
  getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey,
} from '@/api/generated/transactions/transactions'
import { TransferPairRequestTransferType } from '@/api/generated/model/transferPairRequestTransferType'
import type { TransactionDetailOut } from '@/api/generated/model/transactionDetailOut'
import type { TransactionOut } from '@/api/generated/model/transactionOut'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import type { PrivacyMode } from '@/lib/format'
import { txDisplayAmount } from '@/domain/transactions'

interface Props {
  householdId: string
  transaction: TransactionDetailOut
  open: boolean
  onClose: () => void
}

export function TransferPairingModal({ householdId, transaction, open, onClose }: Props) {
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [transferType, setTransferType] = useState<'internal' | 'external'>('internal')

  const oppositeDirection = transaction.direction === 'debit' ? 'credit' : 'debit'

  const { data: candidates } =
    useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet(
      householdId,
      {
        direction: oppositeDirection as 'debit' | 'credit',
        date_from: offsetDate(transaction.posted_date ?? transaction.occurred_at.slice(0, 10), -7),
        date_to: offsetDate(transaction.posted_date ?? transaction.occurred_at.slice(0, 10), 7),
      },
      { query: { enabled: open } }
    )

  const { mutateAsync: pairTransfer, isPending } =
    usePairTransferCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdTransferPairPost()

  async function handleConfirm() {
    if (!selectedId) return
    await pairTransfer({
      householdId,
      transactionId: transaction.id,
      data: {
        peer_id: selectedId,
        transfer_type: TransferPairRequestTransferType[transferType],
      },
    })
    await Promise.all([
      qc.invalidateQueries({
        queryKey:
          getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey(
            householdId,
            transaction.id
          ),
      }),
      qc.invalidateQueries({
        queryKey:
          getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey(
            householdId
          ),
      }),
    ])
    onClose()
  }

  if (!open) return null

  const txAmount = Math.abs(parseFloat(transaction.amount))
  const filtered =
    candidates?.filter((c) => {
      if (c.id === transaction.id) return false
      const diff = Math.abs(Math.abs(parseFloat(c.amount)) - txAmount)
      return diff / txAmount < 0.01
    }) ?? []

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200 }}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 201,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          width: 520,
          maxWidth: 'calc(100vw - 32px)',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
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
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Mark as transfer
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

        <div
          style={{ padding: '16px 24px', flexShrink: 0, borderBottom: '1px solid var(--border)' }}
        >
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 8 }}>
            Transfer type
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['internal', 'external'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTransferType(t)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 8,
                  border: `1px solid ${transferType === t ? 'var(--accent)' : 'var(--border)'}`,
                  background:
                    transferType === t
                      ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                      : 'none',
                  color: transferType === t ? 'var(--accent)' : 'var(--fg-secondary)',
                  fontSize: 12,
                  cursor: 'pointer',
                  fontWeight: transferType === t ? 500 : 400,
                }}
              >
                {t === 'internal' ? 'Internal (same household)' : 'External (outside)'}
              </button>
            ))}
          </div>
        </div>

        <div
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: '12px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>
            Matching transactions (same amount, within 7 days)
          </div>

          {filtered.length === 0 && (
            <div
              style={{
                padding: '24px 0',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              No matching transactions found
            </div>
          )}

          {filtered.map((tx) => (
            <CandidateRow
              key={tx.id}
              tx={tx}
              privacyMode={privacyMode}
              selected={selectedId === tx.id}
              onSelect={() => setSelectedId(tx.id === selectedId ? null : tx.id)}
            />
          ))}
        </div>

        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <button
            type="button"
            disabled={!selectedId || isPending}
            onClick={() => void handleConfirm()}
            style={{
              width: '100%',
              padding: '10px',
              borderRadius: 8,
              border: 'none',
              background: selectedId ? 'var(--accent)' : 'var(--border)',
              color: selectedId ? 'var(--accent-fg)' : 'var(--fg-muted)',
              fontSize: 13,
              fontWeight: 500,
              cursor: selectedId && !isPending ? 'pointer' : 'not-allowed',
            }}
          >
            {isPending ? 'Pairing...' : 'Confirm transfer pair'}
          </button>
        </div>
      </div>
    </>
  )
}

function CandidateRow({
  tx,
  privacyMode,
  selected,
  onSelect,
}: {
  tx: TransactionOut
  privacyMode: PrivacyMode
  selected: boolean
  onSelect: () => void
}) {
  const amt = txDisplayAmount(tx)
  const isIncome = tx.direction === 'credit'
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        borderRadius: 10,
        border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
        background: selected
          ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
          : 'var(--bg-primary)',
        cursor: 'pointer',
        width: '100%',
        textAlign: 'left' as const,
      }}
    >
      {selected && <Check size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--fg-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {tx.merchant_name ?? tx.description}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{tx.posted_date}</div>
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 500,
          fontFamily: 'var(--font-mono)',
          color: isIncome ? 'var(--success)' : 'var(--fg-primary)',
          flexShrink: 0,
        }}
      >
        {isIncome ? '+' : ''}
        {fmt(amt, privacyMode, tx.currency)}
      </div>
    </button>
  )
}

function offsetDate(dateStr: string | null | undefined, days: number): string {
  const safe = dateStr ?? new Date().toISOString().slice(0, 10)
  const parts = safe.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  const date = new Date(y, m - 1, d)
  date.setDate(date.getDate() + days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
