import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useMeApiV1AuthMeGet,
  useGetHouseholdApiV1HouseholdsHouseholdIdGet,
  useListMembersApiV1HouseholdsHouseholdIdMembersGet,
  useArchiveHouseholdApiV1HouseholdsHouseholdIdDelete,
  useLogoutApiV1AuthLogoutPost,
} from '@/api/generated/households/households'
import type { MembershipOut } from '@/api/generated/model/membershipOut'
import { useAuthStore } from '@/store'

export function DangerZonePage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const clearUser = useAuthStore((s) => s.clearUser)

  const { data: me } = useMeApiV1AuthMeGet()
  const hid = me?.household_id ?? ''

  const { data: household } = useGetHouseholdApiV1HouseholdsHouseholdIdGet(hid, {
    query: { enabled: !!hid },
  })
  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(hid, {
    query: { enabled: !!hid },
  })

  const isOwner = (members as MembershipOut[]).find((m) => m.user_id === me?.id)?.role === 'OWNER'

  const archiveHousehold = useArchiveHouseholdApiV1HouseholdsHouseholdIdDelete()
  const logoutMutation = useLogoutApiV1AuthLogoutPost()

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmName, setConfirmName] = useState('')
  const [archiveError, setArchiveError] = useState<string | null>(null)

  const householdName = household?.name ?? ''
  const canConfirm = confirmName === householdName

  const handleArchive = async () => {
    if (!canConfirm || !hid) return
    setArchiveError(null)
    try {
      await archiveHousehold.mutateAsync({ householdId: hid })
      void qc.clear()
      try {
        await logoutMutation.mutateAsync()
      } catch {
        // best-effort
      }
      clearUser()
      navigate('/login', { replace: true })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setArchiveError(detail ?? 'Failed to archive household')
      setConfirmOpen(false)
      setConfirmName('')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 520 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Danger zone
        </h2>
        <p style={{ fontSize: 13, color: 'var(--fg-muted)', marginTop: 6 }}>
          These actions are permanent and cannot be undone.
        </p>
      </div>

      {/* Archive household */}
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid color-mix(in oklch, var(--danger) 40%, transparent)',
          borderRadius: 12,
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--danger)' }}>
            Archive household
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-secondary)', marginTop: 4 }}>
            Permanently archives this household and all associated data. All members will lose
            access. This cannot be reversed through the app.
          </div>
        </div>

        {!isOwner && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--fg-muted)',
              background: 'var(--bg-secondary)',
              borderRadius: 8,
              padding: '8px 12px',
            }}
          >
            Only the household owner can archive the household.
          </div>
        )}

        {archiveError && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{archiveError}</div>}

        {isOwner && !confirmOpen && (
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            style={{
              alignSelf: 'flex-start',
              padding: '8px 16px',
              borderRadius: 8,
              border: '1px solid color-mix(in oklch, var(--danger) 60%, transparent)',
              background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
              color: 'var(--danger)',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Archive household
          </button>
        )}

        {isOwner && confirmOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 13, color: 'var(--fg-secondary)' }}>
              Type{' '}
              <span style={{ fontWeight: 600, color: 'var(--fg-primary)' }}>{householdName}</span>{' '}
              to confirm.
            </div>
            <input
              type="text"
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
              placeholder={householdName}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
                fontFamily: 'var(--font-sans)',
              }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={() => void handleArchive()}
                disabled={!canConfirm || archiveHousehold.isPending}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: canConfirm ? 'var(--danger)' : 'var(--bg-secondary)',
                  color: canConfirm ? '#fff' : 'var(--fg-muted)',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: canConfirm && !archiveHousehold.isPending ? 'pointer' : 'not-allowed',
                  opacity: archiveHousehold.isPending ? 0.7 : 1,
                  fontFamily: 'var(--font-sans)',
                  transition: 'background 0.15s',
                }}
              >
                {archiveHousehold.isPending ? 'Archiving...' : 'Confirm archive'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmOpen(false)
                  setConfirmName('')
                }}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--fg-secondary)',
                  fontSize: 13,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
