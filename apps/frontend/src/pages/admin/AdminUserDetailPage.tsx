import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetUserApiV1AdminUsersUserIdGet,
  useListHouseholdsApiV1AdminHouseholdsGet,
  useDeleteUserApiV1AdminUsersUserIdDelete,
  usePromoteUserApiV1AdminUsersUserIdPromotePost,
  useDemoteUserApiV1AdminUsersUserIdDemotePost,
  useAssignHouseholdApiV1AdminUsersUserIdAssignHouseholdPost,
  useForceLogoutApiV1AdminUsersUserIdForceLogoutPost,
  getListUsersApiV1AdminUsersGetQueryKey,
} from '@/api/generated/admin/admin'

const A = {
  bg: '#0a0f1a',
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
  danger: '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
}

function relativeTime(iso: string): string {
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    return `${Math.floor(diffHr / 24)}d ago`
  } catch {
    return iso
  }
}

type StepUpType = 'promote' | 'demote' | 'assign' | 'delete'

interface AssignModalProps {
  onConfirm: (householdId: string, role: string) => void
  onCancel: () => void
}

function AssignModal({ onConfirm, onCancel }: AssignModalProps) {
  const { data: households } = useListHouseholdsApiV1AdminHouseholdsGet()
  const [selected, setSelected] = useState('')
  const [role, setRole] = useState('member')
  const [search, setSearch] = useState('')
  const filtered = (households?.items ?? []).filter((h) =>
    h.name.toLowerCase().includes(search.toLowerCase())
  )
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: 24,
          width: 400,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Assign to household</div>
        <input
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: '7px 10px',
            borderRadius: 6,
            fontSize: 13,
            background: A.bg,
            border: `1px solid ${A.border}`,
            color: A.fg,
            outline: 'none',
          }}
        />
        <div
          style={{
            maxHeight: 180,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {filtered.map((h) => (
            <button
              key={h.id}
              onClick={() => setSelected(h.id)}
              style={{
                padding: '7px 10px',
                borderRadius: 6,
                textAlign: 'left',
                cursor: 'pointer',
                background: selected === h.id ? `rgba(59,130,246,0.15)` : 'transparent',
                border: `1px solid ${selected === h.id ? A.accent : A.border}`,
                color: A.fg,
                fontSize: 13,
              }}
            >
              {h.name}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {['member', 'owner'].map((r) => (
            <button
              key={r}
              onClick={() => setRole(r)}
              style={{
                flex: 1,
                padding: '6px 0',
                borderRadius: 6,
                cursor: 'pointer',
                background: role === r ? `rgba(59,130,246,0.15)` : 'transparent',
                border: `1px solid ${role === r ? A.accent : A.border}`,
                color: role === r ? A.accent : A.fgMuted,
                fontSize: 12,
                fontWeight: 500,
                textTransform: 'capitalize',
              }}
            >
              {r}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '7px 14px',
              borderRadius: 6,
              background: 'transparent',
              border: `1px solid ${A.border}`,
              color: A.fgMuted,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            disabled={!selected}
            onClick={() => onConfirm(selected, role)}
            style={{
              padding: '7px 14px',
              borderRadius: 6,
              background: selected ? A.accent : A.border,
              border: 'none',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              cursor: selected ? 'pointer' : 'not-allowed',
              opacity: selected ? 1 : 0.5,
            }}
          >
            Assign
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: user, isLoading } = useGetUserApiV1AdminUsersUserIdGet(id ?? '')
  const deleteUser = useDeleteUserApiV1AdminUsersUserIdDelete()
  const promote = usePromoteUserApiV1AdminUsersUserIdPromotePost()
  const demote = useDemoteUserApiV1AdminUsersUserIdDemotePost()
  const assign = useAssignHouseholdApiV1AdminUsersUserIdAssignHouseholdPost()
  const forceLogout = useForceLogoutApiV1AdminUsersUserIdForceLogoutPost()

  const [showAssign, setShowAssign] = useState(false)
  const [deleteInput, setDeleteInput] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [forceLogoutConfirm, setForceLogoutConfirm] = useState(false)

  function invalidate() {
    void qc.invalidateQueries({ queryKey: getListUsersApiV1AdminUsersGetQueryKey() })
  }

  async function executeStepUp(type: StepUpType) {
    if (!id) return
    if (type === 'promote') {
      await promote.mutateAsync({ userId: id })
      invalidate()
    } else if (type === 'demote') {
      await demote.mutateAsync({ userId: id })
      invalidate()
    } else if (type === 'assign') {
      setShowAssign(true)
    } else if (type === 'delete') {
      setShowDeleteConfirm(true)
    }
  }

  if (isLoading || !user) {
    return <div style={{ padding: 32, color: A.fgMuted }}>Loading...</div>
  }

  const isUnassigned = user.household_count === 0

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 760 }}>
      {showAssign && (
        <AssignModal
          onCancel={() => setShowAssign(false)}
          onConfirm={async (householdId, role) => {
            if (!id) return
            await assign.mutateAsync({
              userId: id,
              data: { household_id: householdId, role: role as 'member' | 'owner' },
            })
            setShowAssign(false)
            invalidate()
          }}
        />
      )}

      {showDeleteConfirm && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: 24,
              width: 420,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.danger }}>Delete account</div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              Permanently delete {user.display_name}'s account? Transaction attribution will be
              removed. This cannot be undone.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, color: A.fgMuted }}>
                Type email to confirm: <strong style={{ color: A.fg }}>{user.email}</strong>
              </label>
              <input
                value={deleteInput}
                onChange={(e) => setDeleteInput(e.target.value)}
                style={{
                  padding: '7px 10px',
                  borderRadius: 6,
                  fontSize: 13,
                  background: A.bg,
                  border: `1px solid ${A.border}`,
                  color: A.fg,
                  outline: 'none',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false)
                  setDeleteInput('')
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: 'transparent',
                  border: `1px solid ${A.border}`,
                  color: A.fgMuted,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                disabled={deleteInput !== user.email}
                onClick={async () => {
                  if (!id) return
                  await deleteUser.mutateAsync({ userId: id })
                  navigate('/admin/users', { replace: true })
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: deleteInput === user.email ? A.danger : A.border,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: deleteInput === user.email ? 'pointer' : 'not-allowed',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {forceLogoutConfirm && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: 24,
              width: 380,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Force logout</div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              Log out all sessions for {user.display_name}?
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setForceLogoutConfirm(false)}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: 'transparent',
                  border: `1px solid ${A.border}`,
                  color: A.fgMuted,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (!id) return
                  await forceLogout.mutateAsync({ userId: id })
                  setForceLogoutConfirm(false)
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: A.danger,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>
              {user.display_name}
            </h1>
            {user.is_app_admin && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: 99,
                  background: `rgba(59,130,246,0.15)`,
                  color: A.accent,
                }}
              >
                ADMIN
              </span>
            )}
            {isUnassigned && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  padding: '1px 6px',
                  borderRadius: 99,
                  background: `rgba(245,158,11,0.15)`,
                  color: A.warning,
                }}
              >
                Unassigned
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, color: A.fgMuted, marginTop: 4 }}>{user.email}</div>
        </div>
      </div>

      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20, alignItems: 'start' }}
      >
        {/* Main info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Memberships */}
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: '18px 20px',
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: A.fgMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 12,
              }}
            >
              Household Memberships
            </div>
            {user.household_count === 0 ? (
              <div style={{ fontSize: 13, color: A.warning }}>Unassigned — no household</div>
            ) : (
              <div style={{ fontSize: 13, color: A.fgMuted }}>
                {user.household_count} household(s)
              </div>
            )}
          </div>

          {/* Account info */}
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: '18px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: A.fgMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              Account
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Created</span>
              <span style={{ fontSize: 13, color: A.fg }}>{relativeTime(user.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div
          style={{
            background: A.bgRaised,
            border: `1px solid ${A.border}`,
            borderRadius: 10,
            padding: '18px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: A.fgMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 4,
            }}
          >
            Actions
          </div>
          {[
            {
              label: user.is_app_admin ? 'Demote admin' : 'Promote to admin',
              action: () => void executeStepUp(user.is_app_admin ? 'demote' : 'promote'),
              color: A.fg,
            },
            {
              label: 'Assign to household',
              action: () => void executeStepUp('assign'),
              color: A.fg,
            },
            {
              label: 'Force logout all sessions',
              action: () => setForceLogoutConfirm(true),
              color: A.fg,
            },
            {
              label: 'Delete account',
              action: () => void executeStepUp('delete'),
              color: A.danger,
            },
          ].map(({ label, action, color }) => (
            <button
              key={label}
              onClick={action}
              style={{
                padding: '8px 12px',
                borderRadius: 6,
                textAlign: 'left',
                cursor: 'pointer',
                background: 'transparent',
                border: `1px solid ${color === A.danger ? A.danger : A.border}`,
                color,
                fontSize: 13,
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
