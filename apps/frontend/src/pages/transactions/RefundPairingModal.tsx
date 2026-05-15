import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetRefundCandidatesApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsTransactionIdRefundCandidatesGet,
  usePairRefundCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdRefundPairPost,
  getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey,
  getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey,
} from '@/api/generated/transactions/transactions'
import type { TransactionDetailOut } from '@/api/generated/model/transactionDetailOut'
import type { RefundCandidateOut } from '@/api/generated/model/refundCandidateOut'
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

export function RefundPairingModal({ householdId, transaction, open, onClose }: Props) {
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: candidates } =
    useGetRefundCandidatesApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsTransactionIdRefundCandidatesGet(
      householdId,
      transaction.account_id,
      transaction.id,
      undefined,
      { query: { enabled: open } }
    )

  const { mutateAsync: pairRefund, isPending } =
    usePairRefundCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdRefundPairPost()

  async function handleConfirm() {
    if (!selectedId) return
    await pairRefund({
      householdId,
      transactionId: transaction.id,
      data: { peer_id: selectedId },
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
            Mark as refund
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
            Refund candidates (opposite direction, within 30 days)
          </div>

          {!candidates && (
            <div
              style={{
                padding: '24px 0',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              Loading...
            </div>
          )}

          {candidates && candidates.length === 0 && (
            <div
              style={{
                padding: '24px 0',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              No refund candidates found
            </div>
          )}

          {candidates?.map((candidate) => (
            <RefundCandidateRow
              key={candidate.transaction.id}
              candidate={candidate}
              privacyMode={privacyMode}
              selected={selectedId === candidate.transaction.id}
              onSelect={() =>
                setSelectedId(
                  candidate.transaction.id === selectedId ? null : candidate.transaction.id
                )
              }
            />
          ))}
        </div>

        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
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
            {isPending ? 'Pairing...' : 'Confirm refund pair'}
          </button>
        </div>
      </div>
    </>
  )
}

function RefundCandidateRow({
  candidate,
  privacyMode,
  selected,
  onSelect,
}: {
  candidate: RefundCandidateOut
  privacyMode: PrivacyMode
  selected: boolean
  onSelect: () => void
}) {
  const tx = candidate.transaction
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
        <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
          {tx.posted_date} &middot; {candidate.days_apart}d apart
        </div>
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
