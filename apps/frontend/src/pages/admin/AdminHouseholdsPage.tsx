import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useListHouseholdsApiV1AdminHouseholdsGet,
  getListHouseholdsApiV1AdminHouseholdsGetQueryKey,
} from '@/api/generated/admin/admin'
import { useCreateHouseholdApiV1HouseholdsPost } from '@/api/generated/households/households'

const A = {
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
}

function relativeTime(iso: string): string {
  try {
    const diffHr = (Date.now() - new Date(iso).getTime()) / 3_600_000
    if (diffHr < 24) return `${Math.floor(diffHr)}h ago`
    return `${Math.floor(diffHr / 24)}d ago`
  } catch {
    return iso
  }
}

export function AdminHouseholdsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data, isLoading } = useListHouseholdsApiV1AdminHouseholdsGet()
  const households = data?.items ?? []

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCurrency, setNewCurrency] = useState('USD')
  const [createError, setCreateError] = useState<string | null>(null)

  const createHousehold = useCreateHouseholdApiV1HouseholdsPost({
    mutation: {
      onSuccess: async () => {
        await qc.invalidateQueries({
          queryKey: getListHouseholdsApiV1AdminHouseholdsGetQueryKey(),
        })
        setShowCreate(false)
        setNewName('')
        setNewCurrency('USD')
        setCreateError(null)
      },
      onError: () => setCreateError('Failed to create household'),
    },
  })

  function handleCreate() {
    if (!newName.trim()) {
      setCreateError('Name required')
      return
    }
    const currency = newCurrency.trim().toUpperCase()
    if (currency.length !== 3) {
      setCreateError('Currency must be 3 letters')
      return
    }
    createHousehold.mutate({
      data: { name: newName.trim(), home_currency: currency, visibility_mode: 'fully_shared' },
    })
  }

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {showCreate && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 300,
          }}
          onClick={() => setShowCreate(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 12,
              padding: 24,
              width: 380,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Create household</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, color: A.fgMuted }}>Name</label>
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="My household"
                style={inputStyle}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, color: A.fgMuted }}>Home currency</label>
              <input
                value={newCurrency}
                onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
                maxLength={3}
                placeholder="USD"
                style={{ ...inputStyle, width: 80 }}
              />
            </div>
            {createError && <div style={{ fontSize: 12, color: '#ef4444' }}>{createError}</div>}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowCreate(false)}
                style={{
                  ...btnBase,
                  background: 'transparent',
                  border: `1px solid ${A.border}`,
                  color: A.fgMuted,
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createHousehold.isPending}
                style={{
                  ...btnBase,
                  background: A.accent,
                  border: 'none',
                  color: '#fff',
                  opacity: createHousehold.isPending ? 0.7 : 1,
                }}
              >
                {createHousehold.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>Households</h1>
          <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
            All households on this instance
          </p>
        </div>
        <button
          onClick={() => {
            setCreateError(null)
            setShowCreate(true)
          }}
          style={{ ...btnBase, background: A.accent, border: 'none', color: '#fff' }}
        >
          + Create household
        </button>
      </div>

      {isLoading ? (
        <div style={{ color: A.fgMuted, fontSize: 13 }}>Loading...</div>
      ) : (
        <div
          style={{
            background: A.bgRaised,
            border: `1px solid ${A.border}`,
            borderRadius: 10,
            overflow: 'hidden',
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 80px 80px 120px',
              gap: 0,
              padding: '10px 16px',
              borderBottom: `1px solid ${A.border}`,
            }}
          >
            {['Name', 'Visibility', 'Members', 'Accounts', 'Created'].map((h) => (
              <div
                key={h}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: A.fgMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {h}
              </div>
            ))}
          </div>
          {households.length === 0 ? (
            <div style={{ padding: '20px 16px', fontSize: 13, color: A.fgMuted }}>
              No households
            </div>
          ) : (
            households.map((h, i) => (
              <div
                key={h.id}
                onClick={() => navigate(`/admin/households/${h.id}`)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 120px 80px 80px 120px',
                  gap: 0,
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderTop: i === 0 ? 'none' : `1px solid ${A.border}`,
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.02)'
                }}
                onMouseLeave={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'transparent'
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 500, color: A.fg }}>{h.name}</span>
                <span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 99,
                      background: `rgba(59,130,246,0.12)`,
                      color: A.accent,
                    }}
                  >
                    {h.visibility_mode}
                  </span>
                </span>
                <span style={{ fontSize: 13, color: A.fg }}>{h.member_count}</span>
                <span style={{ fontSize: 13, color: A.fg }}>{h.account_count}</span>
                <span style={{ fontSize: 13, color: A.fgMuted }}>{relativeTime(h.created_at)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '7px 10px',
  borderRadius: 7,
  border: `1px solid #1f2937`,
  background: '#0a0f1a',
  color: '#f9fafb',
  fontSize: 13,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

const btnBase: React.CSSProperties = {
  padding: '7px 14px',
  borderRadius: 7,
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
}
