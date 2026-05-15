import { useState } from 'react'
import { X, RefreshCw, ArrowLeftRight, CornerUpLeft, Archive, AlertTriangle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import type { PrivacyMode } from '@/lib/format'
import {
  useGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGet,
  useTransitionStateCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdStatePatch,
  useArchiveTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdDelete,
  getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey,
  getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey,
} from '@/api/generated/transactions/transactions'
import { useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet } from '@/api/generated/classification/classification'
import { useListMembersApiV1HouseholdsHouseholdIdMembersGet } from '@/api/generated/households/households'
import type { SplitAllocationOut } from '@/api/generated/model/splitAllocationOut'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import { categoryColor, txDisplayAmount } from '@/domain/transactions'
import { SplitEditor } from './SplitEditor'
import { TransferPairingModal } from './TransferPairingModal'
import { RefundPairingModal } from './RefundPairingModal'

interface Props {
  householdId: string
  transactionId: string | null
  onClose: () => void
  onOpenTransaction: (id: string) => void
}

export function TransactionDetail({
  householdId,
  transactionId,
  onClose,
  onOpenTransaction,
}: Props) {
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const qc = useQueryClient()
  const [showSplitEditor, setShowSplitEditor] = useState(false)
  const [showTransferModal, setShowTransferModal] = useState(false)
  const [showRefundModal, setShowRefundModal] = useState(false)
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false)

  const isOpen = !!transactionId

  const { data: tx, isLoading } =
    useGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGet(
      householdId,
      transactionId ?? '',
      { query: { enabled: isOpen } }
    )

  const { data: categories = [] } = useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet(
    householdId,
    { query: { enabled: isOpen } }
  )

  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(householdId, {
    query: { enabled: isOpen },
  })

  const { mutateAsync: transitionState, isPending: transitioning } =
    useTransitionStateCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdStatePatch()

  const { mutateAsync: archiveTx, isPending: archiving } =
    useArchiveTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdDelete()

  async function handleReconcile() {
    if (!tx) return
    await transitionState({
      householdId,
      transactionId: tx.id,
      data: { state: 'reconciled' },
    })
    await Promise.all([
      qc.invalidateQueries({
        queryKey:
          getGetTransactionCrossAccountApiV1HouseholdsHouseholdIdTransactionsTransactionIdGetQueryKey(
            householdId,
            tx.id
          ),
      }),
      qc.invalidateQueries({
        queryKey:
          getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey(
            householdId
          ),
      }),
    ])
  }

  async function handleArchive() {
    if (!tx) return
    await archiveTx({ householdId, transactionId: tx.id })
    await qc.invalidateQueries({
      queryKey:
        getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey(
          householdId
        ),
    })
    onClose()
  }

  const isMobile = window.innerWidth < 768

  const sheetStyle: React.CSSProperties = isMobile
    ? {
        position: 'fixed',
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 150,
        background: 'var(--bg-elevated)',
        borderTop: '1px solid var(--border)',
        borderRadius: '16px 16px 0 0',
        maxHeight: '88vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transform: isOpen ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 0.3s cubic-bezier(0.22, 1, 0.36, 1)',
      }
    : {
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        zIndex: 150,
        width: 480,
        background: 'var(--bg-elevated)',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.3s cubic-bezier(0.22, 1, 0.36, 1)',
      }

  const displayAmt = tx ? txDisplayAmount(tx) : 0
  const isIncome = tx?.direction === 'credit'

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 149,
            transition: 'opacity 0.3s',
          }}
        />
      )}

      <div style={sheetStyle}>
        {/* Header */}
        <div
          style={{
            padding: '20px 20px 16px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <div
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}
          >
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase' as const,
                  letterSpacing: '0.07em',
                  fontWeight: 600,
                  marginBottom: 4,
                }}
              >
                Transaction
              </div>
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '-0.02em',
                  color: isIncome ? 'var(--success)' : 'var(--fg-primary)',
                }}
              >
                {isIncome ? '+' : ''}
                {tx ? fmt(displayAmt, privacyMode, tx.currency) : '—'}
              </div>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'var(--fg-primary)',
                  marginTop: 4,
                  whiteSpace: 'nowrap' as const,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {tx ? (tx.merchant_name ?? tx.description) : ''}
              </div>
            </div>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: 6,
                flexShrink: 0,
              }}
            >
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
              {tx && (
                <div style={{ display: 'flex', gap: 6 }}>
                  <StateBadge state={tx.state} />
                  <DirBadge direction={tx.direction} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Body */}
        <div
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {isLoading && (
            <div
              style={{
                padding: '48px 0',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              Loading...
            </div>
          )}

          {tx && (
            <>
              {/* Metadata */}
              <Section title="Details">
                <MetaRow label="Posted" value={tx.posted_date} />
                {tx.pending_date && <MetaRow label="Pending" value={tx.pending_date} />}
                <MetaRow label="Description" value={tx.description} />
                {tx.external_id && <MetaRow label="External ID" value={tx.external_id} muted />}
                {tx.recurrence_id && (
                  <MetaRow label="Recurrence" value="Linked" icon={<RefreshCw size={11} />} />
                )}
              </Section>

              {/* Splits */}
              <Section
                title="Allocation"
                action={
                  <button
                    type="button"
                    onClick={() => setShowSplitEditor(true)}
                    style={{
                      fontSize: 11,
                      color: 'var(--accent)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    Edit splits
                  </button>
                }
              >
                <SplitsDisplay
                  splits={tx.splits ?? []}
                  categories={categories}
                  members={members}
                  total={parseFloat(tx.amount)}
                  currency={tx.currency}
                  privacyMode={privacyMode}
                />
              </Section>

              {/* Peers */}
              {tx.transfer_peer_id && (
                <Section title="Transfer">
                  <button
                    type="button"
                    onClick={() => tx.transfer_peer_id && onOpenTransaction(tx.transfer_peer_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-primary)',
                      color: 'var(--fg-primary)',
                      fontSize: 12,
                      cursor: 'pointer',
                      width: '100%',
                      textAlign: 'left' as const,
                    }}
                  >
                    <ArrowLeftRight size={12} style={{ color: 'var(--accent)' }} />
                    View paired transfer
                  </button>
                </Section>
              )}

              {tx.refund_peer_id && (
                <Section title="Refund">
                  <button
                    type="button"
                    onClick={() => tx.refund_peer_id && onOpenTransaction(tx.refund_peer_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-primary)',
                      color: 'var(--fg-primary)',
                      fontSize: 12,
                      cursor: 'pointer',
                      width: '100%',
                      textAlign: 'left' as const,
                    }}
                  >
                    <CornerUpLeft size={12} style={{ color: 'var(--success)' }} />
                    View paired refund
                  </button>
                </Section>
              )}

              {/* Actions */}
              <Section title="Actions">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {tx.state === 'posted' && (
                    <ActionButton
                      icon={<RefreshCw size={13} />}
                      label="Mark as reconciled"
                      onClick={() => void handleReconcile()}
                      disabled={transitioning}
                    />
                  )}
                  {!tx.transfer_peer_id && (
                    <ActionButton
                      icon={<ArrowLeftRight size={13} />}
                      label="Mark as transfer"
                      onClick={() => setShowTransferModal(true)}
                    />
                  )}
                  {!tx.refund_peer_id && (
                    <ActionButton
                      icon={<CornerUpLeft size={13} />}
                      label="Mark as refund"
                      onClick={() => setShowRefundModal(true)}
                    />
                  )}
                  <ActionButton
                    icon={<Archive size={13} />}
                    label="Archive transaction"
                    onClick={() => setShowArchiveConfirm(true)}
                    danger
                  />
                </div>
              </Section>
            </>
          )}
        </div>
      </div>

      {/* Modals */}
      {tx && (
        <>
          <SplitEditor
            householdId={householdId}
            transaction={tx}
            categories={categories}
            members={members}
            open={showSplitEditor}
            onClose={() => setShowSplitEditor(false)}
          />
          <TransferPairingModal
            householdId={householdId}
            transaction={tx}
            open={showTransferModal}
            onClose={() => setShowTransferModal(false)}
          />
          <RefundPairingModal
            householdId={householdId}
            transaction={tx}
            open={showRefundModal}
            onClose={() => setShowRefundModal(false)}
          />
        </>
      )}

      {/* Archive confirm */}
      {showArchiveConfirm && (
        <>
          <div
            onClick={() => setShowArchiveConfirm(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 400 }}
          />
          <div
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 401,
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 14,
              padding: '24px',
              width: 360,
              maxWidth: 'calc(100vw - 32px)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <AlertTriangle
                size={20}
                style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 2 }}
              />
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
                  Archive transaction?
                </div>
                <div
                  style={{ fontSize: 13, color: 'var(--fg-muted)', marginTop: 4, lineHeight: 1.5 }}
                >
                  This will soft-delete the transaction. You can restore it from the admin tools.
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowArchiveConfirm(false)}
                style={{
                  flex: 1,
                  padding: '8px',
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
                disabled={archiving}
                onClick={() => void handleArchive()}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: 8,
                  border: 'none',
                  background: 'var(--danger)',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: archiving ? 'not-allowed' : 'pointer',
                }}
              >
                {archiving ? 'Archiving...' : 'Archive'}
              </button>
            </div>
          </div>
        </>
      )}
    </>
  )
}

function Section({
  title,
  action,
  children,
}: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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
            letterSpacing: '0.07em',
          }}
        >
          {title}
        </div>
        {action}
      </div>
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </div>
  )
}

function MetaRow({
  label,
  value,
  muted = false,
  icon,
}: {
  label: string
  value: string
  muted?: boolean
  icon?: React.ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '9px 12px',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{label}</span>
      <span
        style={{
          fontSize: 12,
          color: muted ? 'var(--fg-muted)' : 'var(--fg-primary)',
          fontWeight: muted ? 400 : 500,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        {icon}
        {value}
      </span>
    </div>
  )
}

function SplitsDisplay({
  splits,
  categories,
  members,
  total,
  currency,
  privacyMode,
}: {
  splits: SplitAllocationOut[]
  categories: { id: string; name: string; color: string | null }[]
  members: { user_id: string; user: { display_name: string } }[]
  total: number
  currency: string
  privacyMode: PrivacyMode
}) {
  if (splits.length === 0) {
    return (
      <div style={{ padding: '12px', fontSize: 12, color: 'var(--fg-muted)', fontStyle: 'italic' }}>
        Uncategorized
      </div>
    )
  }

  return (
    <>
      {splits.map((split, i) => {
        const cat = categories.find((c) => c.id === split.category_id)
        const member = members.find((m) => m.user_id === split.attributed_to_user_id)
        const amt = parseFloat(split.amount)
        const col = cat ? categoryColor(cat.color, cat.name) : 'var(--border)'

        return (
          <div
            key={split.id}
            style={{
              padding: '10px 12px',
              borderBottom: i < splits.length - 1 ? '1px solid var(--border)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <span
              style={{ width: 8, height: 8, borderRadius: '50%', background: col, flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: cat ? 'var(--fg-primary)' : 'var(--fg-muted)',
                }}
              >
                {cat ? cat.name : 'No category'}
              </div>
              {member && (
                <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                  {member.user.display_name}
                </div>
              )}
            </div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 500,
                fontFamily: 'var(--font-mono)',
                color: 'var(--fg-primary)',
                flexShrink: 0,
              }}
            >
              {fmt(amt, privacyMode, currency)}
              {splits.length > 1 && (
                <span style={{ fontSize: 10, color: 'var(--fg-muted)', marginLeft: 4 }}>
                  ({Math.round((amt / total) * 100)}%)
                </span>
              )}
            </div>
          </div>
        )
      })}
    </>
  )
}

function StateBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    pending: 'var(--warning)',
    posted: 'var(--accent)',
    reconciled: 'var(--success)',
  }
  const col = colors[state] ?? 'var(--fg-muted)'
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: `color-mix(in oklch, ${col} 15%, transparent)`,
        color: col,
        textTransform: 'uppercase' as const,
        letterSpacing: '0.04em',
      }}
    >
      {state}
    </span>
  )
}

function DirBadge({ direction }: { direction: string }) {
  const isCredit = direction === 'credit'
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: isCredit
          ? 'color-mix(in oklch, var(--success) 15%, transparent)'
          : 'color-mix(in oklch, var(--danger) 12%, transparent)',
        color: isCredit ? 'var(--success)' : 'var(--danger)',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.04em',
      }}
    >
      {direction}
    </span>
  )
}

function ActionButton({
  icon,
  label,
  onClick,
  disabled = false,
  danger = false,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        borderRadius: 8,
        border: `1px solid ${danger ? 'color-mix(in oklch, var(--danger) 30%, transparent)' : 'var(--border)'}`,
        background: 'none',
        color: danger ? 'var(--danger)' : 'var(--fg-secondary)',
        fontSize: 13,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        width: '100%',
        textAlign: 'left' as const,
      }}
    >
      {icon}
      {label}
    </button>
  )
}
