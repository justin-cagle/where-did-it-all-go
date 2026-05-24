import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useListUsersApiV1AdminUsersGet,
  getListUsersApiV1AdminUsersGetQueryKey,
  getGetOverviewApiV1AdminOverviewGetQueryKey,
  useDeleteUserApiV1AdminUsersUserIdDelete,
  usePromoteUserApiV1AdminUsersUserIdPromotePost,
  useDemoteUserApiV1AdminUsersUserIdDemotePost,
  useAssignHouseholdApiV1AdminUsersUserIdAssignHouseholdPost,
  useForceLogoutApiV1AdminUsersUserIdForceLogoutPost,
  useListHouseholdsApiV1AdminHouseholdsGet,
} from '@/api/generated/admin/admin'
import type { AdminUserOut } from '@/api/generated/model'

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

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2)
  const hue = (name.charCodeAt(0) * 37 + name.charCodeAt(1) * 13) % 360
  return (
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        flexShrink: 0,
        background: `hsl(${hue}, 50%, 35%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontWeight: 600,
        color: '#fff',
      }}
    >
      {initials || '?'}
    </div>
  )
}

type ActionPending = {
  type: 'delete' | 'promote' | 'demote' | 'assign'
  userId: string
  userName: string
}

interface AssignModalProps {
  userId: string
  onConfirm: (householdId: string, role: string) => void
  onCancel: () => void
}

function AssignModal({ userId: _userId, onConfirm, onCancel }: AssignModalProps) {
  const { data: households } = useListHouseholdsApiV1AdminHouseholdsGet()
  const [selectedHousehold, setSelectedHousehold] = useState('')
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
          placeholder="Search households..."
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
            maxHeight: 200,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {filtered.map((h) => (
            <button
              key={h.id}
              onClick={() => setSelectedHousehold(h.id)}
              style={{
                padding: '8px 10px',
                borderRadius: 6,
                textAlign: 'left',
                cursor: 'pointer',
                background: selectedHousehold === h.id ? `rgba(59,130,246,0.15)` : 'transparent',
                border: `1px solid ${selectedHousehold === h.id ? A.accent : A.border}`,
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
            disabled={!selectedHousehold}
            onClick={() => onConfirm(selectedHousehold, role)}
            style={{
              padding: '7px 14px',
              borderRadius: 6,
              background: selectedHousehold ? A.accent : A.border,
              border: 'none',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              cursor: selectedHousehold ? 'pointer' : 'not-allowed',
              opacity: selectedHousehold ? 1 : 0.5,
            }}
          >
            Assign
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminUsersPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'unassigned' | 'admins'>(
    searchParams.get('unassigned') === 'true' ? 'unassigned' : 'all'
  )
  const [deleteConfirm, setDeleteConfirm] = useState<{ userId: string; email: string } | null>(null)
  const [deleteInput, setDeleteInput] = useState('')
  const [assignUser, setAssignUser] = useState<string | null>(null)
  const [assignSuccess, setAssignSuccess] = useState<string | null>(null)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

  const params = {
    search: search || undefined,
    unassigned: filter === 'unassigned' ? true : undefined,
    is_admin: filter === 'admins' ? true : undefined,
  }
  const { data, isLoading } = useListUsersApiV1AdminUsersGet(params)

  const deleteUser = useDeleteUserApiV1AdminUsersUserIdDelete()
  const promote = usePromoteUserApiV1AdminUsersUserIdPromotePost()
  const demote = useDemoteUserApiV1AdminUsersUserIdDemotePost()
  const assign = useAssignHouseholdApiV1AdminUsersUserIdAssignHouseholdPost()
  const forceLogout = useForceLogoutApiV1AdminUsersUserIdForceLogoutPost()

  function invalidate() {
    void qc.invalidateQueries({ queryKey: getListUsersApiV1AdminUsersGetQueryKey() })
    void qc.invalidateQueries({ queryKey: getGetOverviewApiV1AdminOverviewGetQueryKey() })
  }

  async function executeAction(action: ActionPending) {
    if (action.type === 'delete') {
      setDeleteConfirm({ userId: action.userId, email: '' })
    } else if (action.type === 'promote') {
      await promote.mutateAsync({ userId: action.userId })
      invalidate()
    } else if (action.type === 'demote') {
      await demote.mutateAsync({ userId: action.userId })
      invalidate()
    } else if (action.type === 'assign') {
      setAssignUser(action.userId)
    }
  }

  const users = data?.items ?? []
  const unassignedCount = users.filter((u) => u.household_count === 0).length

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Delete confirm modal */}
      {deleteConfirm && (
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
              width: 400,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.danger }}>
              Delete user account
            </div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              Permanently delete this account? Transaction attribution will be removed. This cannot
              be undone.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, color: A.fgMuted }}>
                Type the user's email to confirm
              </label>
              <input
                value={deleteInput}
                onChange={(e) => setDeleteInput(e.target.value)}
                placeholder={deleteConfirm.email}
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
                  setDeleteConfirm(null)
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
                disabled={deleteInput !== deleteConfirm.email && deleteConfirm.email !== ''}
                onClick={async () => {
                  await deleteUser.mutateAsync({ userId: deleteConfirm.userId })
                  setDeleteConfirm(null)
                  setDeleteInput('')
                  invalidate()
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
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign modal */}
      {assignUser && (
        <AssignModal
          userId={assignUser}
          onCancel={() => setAssignUser(null)}
          onConfirm={async (householdId, role) => {
            await assign.mutateAsync({
              userId: assignUser,
              data: { household_id: householdId, role: role as 'member' | 'owner' },
            })
            setAssignUser(null)
            invalidate()
            setAssignSuccess(`User assigned as ${role}.`)
            setTimeout(() => setAssignSuccess(null), 3000)
          }}
        />
      )}

      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>Users</h1>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
          All user accounts on this instance
        </p>
      </div>

      {unassignedCount > 0 && (
        <div
          style={{
            background: `rgba(245,158,11,0.1)`,
            border: `1px solid ${A.warning}`,
            borderRadius: 8,
            padding: '10px 14px',
            fontSize: 13,
            color: A.warning,
          }}
        >
          {unassignedCount} account{unassignedCount !== 1 ? 's' : ''} waiting for household
          assignment
        </div>
      )}

      {assignSuccess && (
        <div
          style={{
            background: `rgba(16,185,129,0.1)`,
            border: `1px solid ${A.success}`,
            borderRadius: 8,
            padding: '10px 14px',
            fontSize: 13,
            color: A.success,
          }}
        >
          {assignSuccess}
        </div>
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by email or name..."
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 13,
            background: A.bgRaised,
            border: `1px solid ${A.border}`,
            color: A.fg,
            outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 4 }}>
          {(['all', 'unassigned', 'admins'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                background: filter === f ? `rgba(59,130,246,0.15)` : 'transparent',
                border: `1px solid ${filter === f ? A.accent : A.border}`,
                color: filter === f ? A.accent : A.fgMuted,
                textTransform: 'capitalize',
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ color: A.fgMuted, fontSize: 13 }}>Loading...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {users.map((user) => (
            <UserRow
              key={user.id}
              user={user}
              menuOpen={openMenuId === user.id}
              onToggleMenu={() => setOpenMenuId(openMenuId === user.id ? null : user.id)}
              onView={() => navigate(`/admin/users/${user.id}`)}
              onAssign={() => {
                void executeAction({ type: 'assign', userId: user.id, userName: user.display_name })
                setOpenMenuId(null)
              }}
              onPromote={() => {
                void executeAction({
                  type: 'promote',
                  userId: user.id,
                  userName: user.display_name,
                })
                setOpenMenuId(null)
              }}
              onDemote={() => {
                void executeAction({ type: 'demote', userId: user.id, userName: user.display_name })
                setOpenMenuId(null)
              }}
              onForceLogout={async () => {
                await forceLogout.mutateAsync({ userId: user.id })
                setOpenMenuId(null)
              }}
              onDelete={() => {
                setDeleteConfirm({ userId: user.id, email: user.email })
                setOpenMenuId(null)
              }}
            />
          ))}
          {users.length === 0 && (
            <div style={{ fontSize: 13, color: A.fgMuted, padding: '16px 0' }}>No users found</div>
          )}
        </div>
      )}
    </div>
  )
}

interface UserRowProps {
  user: AdminUserOut
  menuOpen: boolean
  onToggleMenu: () => void
  onView: () => void
  onAssign: () => void
  onPromote: () => void
  onDemote: () => void
  onForceLogout: () => void
  onDelete: () => void
}

function UserRow({
  user,
  menuOpen,
  onToggleMenu,
  onView,
  onAssign,
  onPromote,
  onDemote,
  onForceLogout,
  onDelete,
}: UserRowProps) {
  const isUnassigned = user.household_count === 0

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        background: '#111827',
        border: `1px solid ${A.border}`,
        borderRadius: 8,
        position: 'relative',
      }}
    >
      <Avatar name={user.display_name} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: A.fg }}>{user.display_name}</span>
          <span style={{ fontSize: 12, color: A.fgMuted }}>{user.email}</span>
          {user.is_app_admin && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 99,
                background: `rgba(59,130,246,0.15)`,
                color: A.accent,
                letterSpacing: '0.04em',
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
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, color: A.fgMuted }}>
          {user.household_count} household{user.household_count !== 1 ? 's' : ''}
        </span>

        <div style={{ position: 'relative' }}>
          <button
            onClick={onToggleMenu}
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: `1px solid ${A.border}`,
              color: A.fgMuted,
              cursor: 'pointer',
              fontSize: 16,
            }}
          >
            ⋯
          </button>
          {menuOpen && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: '100%',
                marginTop: 4,
                background: A.bgRaised,
                border: `1px solid ${A.border}`,
                borderRadius: 8,
                padding: 4,
                minWidth: 160,
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
              }}
            >
              {[
                { label: 'View detail', action: onView, color: A.fg },
                { label: 'Assign to household', action: onAssign, color: A.fg },
                {
                  label: user.is_app_admin ? 'Demote admin' : 'Promote to admin',
                  action: user.is_app_admin ? onDemote : onPromote,
                  color: A.fg,
                },
                { label: 'Force logout', action: onForceLogout, color: A.fg },
                { label: 'Delete', action: onDelete, color: A.danger },
              ].map(({ label, action, color }) => (
                <button
                  key={label}
                  onClick={action}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 4,
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: 'transparent',
                    border: 'none',
                    fontSize: 13,
                    color,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
