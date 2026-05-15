import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Pencil, Check, X, Trash2, RefreshCw, ExternalLink } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useHousehold } from '@/hooks/use-household'
import {
  useGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGet,
  useUpdateAccountApiV1HouseholdsHouseholdIdAccountsAccountIdPatch,
  useArchiveAccountApiV1HouseholdsHouseholdIdAccountsAccountIdDelete,
  useGetDebtAnnotationApiV1HouseholdsHouseholdIdAccountsAccountIdDebtGet,
  useListDebtBalancesApiV1HouseholdsHouseholdIdAccountsAccountIdDebtBalancesGet,
  getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey,
  getGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGetQueryKey,
} from '@/api/generated/accounts/accounts'
import { useListTransactionsForAccountApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsGet } from '@/api/generated/transactions/transactions'
import type { TransactionOut } from '@/api/generated/model/transactionOut'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import type { PrivacyMode } from '@/lib/format'
import { isLiabilityType, accountTypeLabel } from '@/domain/accounts'
import { ApiError } from '@/api/client'

function TypeBadge({ type }: { type: string }) {
  const isLiab = isLiabilityType(type)
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '3px 9px',
        borderRadius: 99,
        background: isLiab
          ? 'color-mix(in oklch, var(--danger) 14%, transparent)'
          : 'color-mix(in oklch, var(--accent) 14%, transparent)',
        color: isLiab ? 'var(--danger)' : 'var(--accent)',
        letterSpacing: '0.03em',
        textTransform: 'uppercase' as const,
      }}
    >
      {accountTypeLabel(type)}
    </span>
  )
}

function TxRow({ tx, privacyMode }: { tx: TransactionOut; privacyMode: PrivacyMode }) {
  const isIncome = tx.direction === 'credit'
  const amount = parseFloat(tx.amount)
  const displayAmount = isIncome ? amount : -amount
  const displayName = tx.merchant_name ?? tx.description
  const date = tx.posted_date

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          flexShrink: 0,
          background: isIncome
            ? 'color-mix(in oklch, var(--success) 14%, transparent)'
            : 'color-mix(in oklch, var(--border) 60%, transparent)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: isIncome ? 'var(--success)' : 'var(--fg-muted)',
          }}
        />
      </div>
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
          {displayName}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
          {date}
          {tx.state === 'pending' && ' · pending'}
        </div>
      </div>
      <span
        style={{
          fontSize: 13,
          fontWeight: 500,
          fontFamily: 'var(--font-mono)',
          color: isIncome ? 'var(--success)' : 'var(--fg-primary)',
          flexShrink: 0,
        }}
      >
        {isIncome ? '+' : ''}
        {fmt(displayAmount, privacyMode, tx.currency)}
      </span>
    </div>
  )
}

function DebtSummaryPanel({ householdId, accountId }: { householdId: string; accountId: string }) {
  const { data: annotation } =
    useGetDebtAnnotationApiV1HouseholdsHouseholdIdAccountsAccountIdDebtGet(householdId, accountId)
  const { data: balances } =
    useListDebtBalancesApiV1HouseholdsHouseholdIdAccountsAccountIdDebtBalancesGet(
      householdId,
      accountId
    )

  if (!annotation) return null

  const currentBalance = balances?.[0]
  const aprDisplay = currentBalance ? `${(parseFloat(currentBalance.apr) * 100).toFixed(2)}%` : null

  const strategyLabel: Record<string, string> = {
    fixed_amount: 'Fixed amount',
    percentage_of_balance: 'Percentage of balance',
    from_statement: 'From statement',
  }

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--fg-muted)',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
        }}
      >
        Debt details
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {aprDisplay && <StatItem label="APR" value={aprDisplay} />}
        {annotation.minimum_payment_strategy && (
          <StatItem
            label="Min. payment"
            value={
              strategyLabel[annotation.minimum_payment_strategy] ??
              annotation.minimum_payment_strategy
            }
          />
        )}
        {annotation.statement_day && (
          <StatItem label="Statement day" value={String(annotation.statement_day)} />
        )}
        {annotation.due_day && <StatItem label="Due day" value={String(annotation.due_day)} />}
      </div>
      <Link
        to="/debts"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 12,
          color: 'var(--accent)',
          textDecoration: 'none',
        }}
      >
        View debt plans <ExternalLink size={11} />
      </Link>
    </div>
  )
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-primary)' }}>{value}</span>
    </div>
  )
}

function BalanceHistoryPlaceholder() {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--fg-muted)',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
        }}
      >
        Balance history — 90 days
      </span>
      <div style={{ height: 140, position: 'relative' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={[]}>
            <XAxis dataKey="date" hide />
            <YAxis hide />
            <Tooltip />
            <Line type="monotone" dataKey="balance" stroke="var(--accent)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
            Balance history unavailable
          </span>
        </div>
      </div>
    </div>
  )
}

function UpdateBalancePanel({
  householdId,
  accountId,
  currentBalance,
  currency,
  onUpdated,
}: {
  householdId: string
  accountId: string
  currentBalance: string
  currency: string
  onUpdated: () => void
}) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const updateAccount = useUpdateAccountApiV1HouseholdsHouseholdIdAccountsAccountIdPatch()

  const currentNum = parseFloat(currentBalance)
  const newNum = parseFloat(value)
  const delta = !isNaN(newNum) && value.trim() !== '' ? newNum - currentNum : null

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSave = async () => {
    if (!value.trim() || isNaN(newNum)) {
      setError('Enter a valid amount')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await updateAccount.mutateAsync({
        householdId,
        accountId,
        data: { current_balance: value.trim() },
      })
      await queryClient.invalidateQueries({
        queryKey: getGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGetQueryKey(
          householdId,
          accountId
        ),
      })
      await queryClient.invalidateQueries({
        queryKey: getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey(householdId),
      })
      onUpdated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>
        Update balance
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={currentBalance}
          style={{
            flex: 1,
            padding: '8px 10px',
            borderRadius: 7,
            border: '1px solid var(--border)',
            background: 'var(--bg-primary)',
            color: 'var(--fg-primary)',
            fontSize: 14,
            fontFamily: 'var(--font-mono)',
            outline: 'none',
          }}
        />
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '0 10px',
            fontSize: 12,
            color: 'var(--fg-muted)',
            border: '1px solid var(--border)',
            borderRadius: 7,
            background: 'var(--bg-secondary)',
          }}
        >
          {currency}
        </span>
      </div>
      {delta !== null && (
        <span
          style={{
            fontSize: 12,
            color: delta >= 0 ? 'var(--success)' : 'var(--danger)',
          }}
        >
          {delta >= 0 ? '+' : ''}
          {fmt(delta, 'off', currency)} from current balance
        </span>
      )}
      {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => void handleSave()}
          disabled={saving}
          style={{
            fontSize: 13,
            fontWeight: 500,
            padding: '7px 14px',
            borderRadius: 7,
            border: 'none',
            background: saving ? 'var(--border)' : 'var(--accent)',
            color: saving ? 'var(--fg-muted)' : 'var(--accent-fg)',
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={onUpdated}
          style={{
            fontSize: 13,
            fontWeight: 500,
            padding: '7px 14px',
            borderRadius: 7,
            border: '1px solid var(--border)',
            background: 'transparent',
            color: 'var(--fg-secondary)',
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export function AccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const navigate = useNavigate()
  const { householdId } = useHousehold()
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const queryClient = useQueryClient()

  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false)
  const [showBalanceUpdate, setShowBalanceUpdate] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const safeAccountId = accountId ?? ''
  const safeHouseholdId = householdId ?? ''

  const {
    data: account,
    isLoading,
    isError,
    refetch,
  } = useGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGet(safeHouseholdId, safeAccountId, {
    query: { enabled: !!householdId && !!accountId },
  })

  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  const { data: transactions } =
    useListTransactionsForAccountApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsGet(
      safeHouseholdId,
      safeAccountId,
      { date_from: thirtyDaysAgo.toISOString().split('T')[0] },
      { query: { enabled: !!householdId && !!accountId } }
    )

  const updateAccount = useUpdateAccountApiV1HouseholdsHouseholdIdAccountsAccountIdPatch()
  const archiveAccount = useArchiveAccountApiV1HouseholdsHouseholdIdAccountsAccountIdDelete()

  const showToast = (msg: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast(msg)
    toastTimer.current = setTimeout(() => setToast(null), 4000)
  }

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current)
    },
    []
  )

  if (!accountId) {
    return <div style={{ color: 'var(--fg-muted)', fontSize: 14 }}>Account not found.</div>
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div
          style={{
            height: 28,
            width: 200,
            background: 'var(--border)',
            borderRadius: 6,
            opacity: 0.6,
          }}
        />
        <div
          style={{
            height: 80,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            opacity: 0.6,
          }}
        />
        <div
          style={{
            height: 160,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            opacity: 0.6,
          }}
        />
      </div>
    )
  }

  if (isError || !account) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          padding: '48px 0',
        }}
      >
        <span style={{ color: 'var(--fg-muted)', fontSize: 14 }}>Failed to load account.</span>
        <button
          onClick={() => void refetch()}
          style={{
            fontSize: 13,
            padding: '7px 16px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  const isDebt = isLiabilityType(account.account_type)
  const isManual = account.is_manual
  const balance = parseFloat(account.current_balance)
  const recentTx = transactions?.slice(0, 20) ?? []

  const handleEditStart = () => {
    setEditName(account.name)
    setIsEditing(true)
    setEditError(null)
  }

  const handleEditSave = async () => {
    if (!editName.trim()) return
    setEditSaving(true)
    setEditError(null)
    try {
      await updateAccount.mutateAsync({
        householdId: safeHouseholdId,
        accountId: safeAccountId,
        data: { name: editName.trim() },
      })
      await queryClient.invalidateQueries({
        queryKey: getGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGetQueryKey(
          safeHouseholdId,
          safeAccountId
        ),
      })
      await queryClient.invalidateQueries({
        queryKey: getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey(safeHouseholdId),
      })
      setIsEditing(false)
      showToast('Account updated')
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : 'Save failed')
    } finally {
      setEditSaving(false)
    }
  }

  const handleArchive = async () => {
    try {
      await archiveAccount.mutateAsync({
        householdId: safeHouseholdId,
        accountId: safeAccountId,
      })
      await queryClient.invalidateQueries({
        queryKey: getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey(safeHouseholdId),
      })
      void navigate('/accounts', { replace: true })
    } catch {
      showToast('Archive failed. Try again.')
      setShowArchiveConfirm(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '10px 16px',
            fontSize: 13,
            color: 'var(--fg-primary)',
            boxShadow: 'var(--shadow)',
            zIndex: 100,
          }}
        >
          {toast}
        </div>
      )}

      <button
        onClick={() => void navigate('/accounts')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--fg-muted)',
          fontSize: 13,
          padding: 0,
          width: 'fit-content',
        }}
      >
        <ArrowLeft size={14} /> Back to accounts
      </button>

      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '20px 22px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 12,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            {account.institution && (
              <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 2 }}>
                {account.institution}
              </div>
            )}
            {isEditing ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  style={{
                    fontSize: 20,
                    fontWeight: 600,
                    color: 'var(--fg-primary)',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '4px 8px',
                    outline: 'none',
                    width: '100%',
                    letterSpacing: '-0.01em',
                  }}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleEditSave()
                    if (e.key === 'Escape') setIsEditing(false)
                  }}
                />
                <button
                  onClick={() => void handleEditSave()}
                  disabled={editSaving}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--success)',
                    display: 'flex',
                  }}
                  title="Save"
                >
                  <Check size={16} />
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--fg-muted)',
                    display: 'flex',
                  }}
                  title="Cancel"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h1
                  style={{
                    fontSize: 20,
                    fontWeight: 600,
                    color: 'var(--fg-primary)',
                    margin: 0,
                    letterSpacing: '-0.01em',
                  }}
                >
                  {account.name}
                </h1>
                <button
                  onClick={handleEditStart}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--fg-muted)',
                    display: 'flex',
                    padding: 2,
                  }}
                  title="Edit name"
                >
                  <Pencil size={13} />
                </button>
              </div>
            )}
            {editError && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{editError}</span>}
          </div>
          <TypeBadge type={account.account_type} />
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span
            style={{
              fontSize: 32,
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '-0.03em',
              color: isDebt ? 'var(--danger)' : 'var(--fg-primary)',
            }}
          >
            {fmt(balance, privacyMode, account.currency)}
          </span>
          <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{account.currency}</span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
          {isManual && (
            <button
              onClick={() => setShowBalanceUpdate((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                fontSize: 12,
                fontWeight: 500,
                padding: '6px 12px',
                borderRadius: 7,
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--fg-secondary)',
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={12} /> Update balance
            </button>
          )}
          <button
            onClick={() => setShowArchiveConfirm(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              fontWeight: 500,
              padding: '6px 12px',
              borderRadius: 7,
              border: '1px solid color-mix(in oklch, var(--danger) 35%, transparent)',
              background: 'transparent',
              color: 'var(--danger)',
              cursor: 'pointer',
            }}
          >
            <Trash2 size={12} /> Archive
          </button>
        </div>

        {showArchiveConfirm && (
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 8,
              background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
              border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <span style={{ fontSize: 13, color: 'var(--fg-primary)', fontWeight: 500 }}>
              Archive this account?
            </span>
            <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              This cannot be undone. The account will be removed from your household.
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => void handleArchive()}
                disabled={archiveAccount.isPending}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: 'none',
                  background: archiveAccount.isPending ? 'var(--border)' : 'var(--danger)',
                  color: 'white',
                  cursor: archiveAccount.isPending ? 'not-allowed' : 'pointer',
                }}
              >
                {archiveAccount.isPending ? 'Archiving…' : 'Archive'}
              </button>
              <button
                onClick={() => setShowArchiveConfirm(false)}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--fg-secondary)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {showBalanceUpdate && isManual && householdId && (
        <UpdateBalancePanel
          householdId={householdId}
          accountId={safeAccountId}
          currentBalance={account.current_balance}
          currency={account.currency}
          onUpdated={() => {
            setShowBalanceUpdate(false)
            showToast('Balance updated')
          }}
        />
      )}

      <BalanceHistoryPlaceholder />

      {isDebt && householdId && (
        <DebtSummaryPanel householdId={householdId} accountId={safeAccountId} />
      )}

      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '16px 18px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 4,
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Recent transactions
          </span>
          <Link
            to={`/transactions?account=${safeAccountId}`}
            style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}
          >
            View all
          </Link>
        </div>

        {recentTx.length === 0 ? (
          <div
            style={{
              padding: '32px 0',
              textAlign: 'center' as const,
              color: 'var(--fg-muted)',
              fontSize: 13,
            }}
          >
            No transactions yet
          </div>
        ) : (
          recentTx.map((tx) => <TxRow key={tx.id} tx={tx} privacyMode={privacyMode} />)
        )}
      </div>
    </div>
  )
}
