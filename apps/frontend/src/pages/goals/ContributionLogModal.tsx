import { useState } from 'react'
import { X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useLogContributionApiV1HouseholdsHouseholdIdGoalsGoalIdContributionsPost } from '@/api/generated/default/default'
import { useListMembersApiV1HouseholdsHouseholdIdMembersGet } from '@/api/generated/households/households'

interface Props {
  householdId: string
  goalId: string
  currency: string
  onClose: () => void
}

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function ContributionLogModal({ householdId, goalId, currency, onClose }: Props) {
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(todayStr())
  const [note, setNote] = useState('')
  const [userId, setUserId] = useState('')
  const [error, setError] = useState('')

  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(householdId, {
    query: { enabled: !!householdId },
  })

  const { mutate: logContribution, isPending } =
    useLogContributionApiV1HouseholdsHouseholdIdGoalsGoalIdContributionsPost({
      mutation: {
        onSuccess: () => {
          void qc.invalidateQueries()
          onClose()
        },
        onError: () => {
          setError('Failed to log contribution. Please try again.')
        },
      },
    })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const parsed = parseFloat(amount)
    if (!amount || isNaN(parsed) || parsed <= 0) {
      setError('Enter a valid positive amount.')
      return
    }
    setError('')
    logContribution({
      householdId,
      goalId,
      data: {
        amount: amount,
        currency,
        contributed_at: date,
        contribution_type: 'manual',
        attributed_to_user_id: userId || undefined,
        note: note || undefined,
      },
    })
  }

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
          width: 420,
          maxWidth: '100%',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderTop: '2px solid var(--accent)',
          borderRadius: 14,
          boxShadow: '0 24px 64px -12px rgba(0,0,0,0.45)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '18px 22px 14px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Log contribution
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

        <form
          onSubmit={handleSubmit}
          style={{ padding: '16px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Amount ({currency}) *
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              required
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--fg-primary)',
                fontSize: 14,
                fontFamily: "'Geist Mono', monospace",
                outline: 'none',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Date *
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
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

          {members.length > 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                Attributed to (optional)
              </label>
              <select
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-elevated)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                  cursor: 'pointer',
                }}
              >
                <option value="">Household</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>
              Note (optional)
            </label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note..."
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

          {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
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
              {isPending ? 'Saving...' : 'Log contribution'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
