import { useEffect, useState } from 'react'
import { UserMinus, Crown, Copy, RefreshCw, X, Mail, MailX, AlertTriangle } from 'lucide-react'
import {
  useGetHouseholdApiV1HouseholdsHouseholdIdGet,
  useListMembersApiV1HouseholdsHouseholdIdMembersGet,
  useRemoveMemberApiV1HouseholdsHouseholdIdMembersUserIdDelete,
  useUpdateHouseholdApiV1HouseholdsHouseholdIdPatch,
  getGetHouseholdApiV1HouseholdsHouseholdIdGetQueryKey,
  useMeApiV1AuthMeGet,
  useCreateInvitationApiV1HouseholdsHouseholdIdInvitationsPost,
  useListInvitationsApiV1HouseholdsHouseholdIdInvitationsGet,
  useResendInvitationApiV1HouseholdsHouseholdIdInvitationsInvitationIdResendPost,
  useRevokeInvitationApiV1HouseholdsHouseholdIdInvitationsInvitationIdRevokePost,
  useGetSmtpStatusApiV1SettingsSmtpStatusGet,
} from '@/api/generated/households/households'
import { useHousehold } from '@/hooks/use-household'
import { useQueryClient } from '@tanstack/react-query'
import type { MembershipOut } from '@/api/generated/model/membershipOut'
import type { InvitationOut } from '@/api/generated/model/invitationOut'
import { VisibilityMode } from '@/api/generated/model/visibilityMode'
import { CurrencySelect } from '@/components/CurrencySelect'

const VISIBILITY_OPTIONS = [
  {
    value: VisibilityMode.fully_shared,
    label: 'Fully shared',
    description: 'All members see all transactions',
  },
  {
    value: VisibilityMode.separate_with_joint_view,
    label: 'Separate + joint',
    description: 'Members have separate views with a shared joint layer',
  },
  {
    value: VisibilityMode.role_based,
    label: 'Role-based',
    description: 'Visibility controlled by member role',
  },
  {
    value: VisibilityMode.admin_controlled,
    label: 'Admin controlled',
    description: 'Owner controls visibility per member',
  },
]

function SettingRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 24,
        padding: '16px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-primary)' }}>{label}</div>
        {description && (
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>{description}</div>
        )}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  )
}

function InlineEdit({ value, onSave }: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await onSave(draft)
      setEditing(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 14, color: 'var(--fg-primary)' }}>{value}</span>
        {saved && <span style={{ fontSize: 12, color: 'var(--success)' }}>Saved</span>}
        <button
          type="button"
          onClick={() => {
            setDraft(value)
            setEditing(true)
            setSaved(false)
          }}
          style={{
            fontSize: 12,
            color: 'var(--accent)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            fontFamily: 'var(--font-sans)',
          }}
        >
          Edit
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoFocus
          style={{
            padding: '6px 10px',
            borderRadius: 8,
            border: `1px solid ${saveError ? 'var(--danger)' : 'var(--border)'}`,
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
            fontSize: 13,
            outline: 'none',
            minWidth: 200,
          }}
        />
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          style={{
            padding: '6px 14px',
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={() => {
            setEditing(false)
            setSaveError(null)
          }}
          style={{
            padding: '6px 14px',
            background: 'none',
            border: '1px solid var(--border)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--fg-muted)',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          Cancel
        </button>
      </div>
      {saveError && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{saveError}</div>}
    </div>
  )
}

function InitialsChip({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2)
  return (
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: 'var(--accent)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <span style={{ color: 'var(--accent-fg)', fontSize: 12, fontWeight: 600 }}>{initials}</span>
    </div>
  )
}

export function HouseholdPage() {
  const { householdId } = useHousehold()
  const hid = householdId ?? ''
  const qc = useQueryClient()
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'member' | 'owner'>('member')
  const [inviteResult, setInviteResult] = useState<InvitationOut | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [pendingCurrency, setPendingCurrency] = useState<string | null>(null)
  const [pendingVisibility, setPendingVisibility] = useState<VisibilityMode | null>(null)
  const [recomputing, setRecomputing] = useState(false)

  useEffect(() => {
    if (!recomputing || !hid) return
    const source = new EventSource('/api/v1/households/events', { withCredentials: true })
    source.addEventListener('fx_recompute_complete', () => {
      setRecomputing(false)
      source.close()
    })
    source.onerror = () => {
      // SSE reconnects automatically
    }
    return () => source.close()
  }, [recomputing, hid])

  const { data: household } = useGetHouseholdApiV1HouseholdsHouseholdIdGet(hid, {
    query: { enabled: !!hid },
  })
  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(hid, {
    query: { enabled: !!hid },
  })
  const { data: me } = useMeApiV1AuthMeGet()
  const { data: invitations = [] } = useListInvitationsApiV1HouseholdsHouseholdIdInvitationsGet(
    hid,
    { status_filter: 'pending' },
    { query: { enabled: !!hid } }
  )
  const { data: smtpStatus } = useGetSmtpStatusApiV1SettingsSmtpStatusGet()
  const removeMember = useRemoveMemberApiV1HouseholdsHouseholdIdMembersUserIdDelete()
  const updateHousehold = useUpdateHouseholdApiV1HouseholdsHouseholdIdPatch()
  const createInvitation = useCreateInvitationApiV1HouseholdsHouseholdIdInvitationsPost()
  const resendInvitation =
    useResendInvitationApiV1HouseholdsHouseholdIdInvitationsInvitationIdResendPost()
  const revokeInvitation =
    useRevokeInvitationApiV1HouseholdsHouseholdIdInvitationsInvitationIdRevokePost()

  const invitationsKey = [`/api/v1/households/${hid}/invitations`]

  if (!household) {
    return <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  const currentMembership = (members as MembershipOut[]).find((m) => m.user_id === me?.id)
  const isOwner = currentMembership?.role === 'owner'

  const handleRemove = async (userId: string) => {
    await removeMember.mutateAsync({ householdId: hid, userId })
    setConfirmRemove(null)
    await qc.invalidateQueries({
      queryKey: [`/api/v1/households/${hid}/members`],
    })
  }

  const handleSaveName = async (name: string) => {
    await updateHousehold.mutateAsync({ householdId: hid, data: { name } })
    await qc.invalidateQueries({
      queryKey: getGetHouseholdApiV1HouseholdsHouseholdIdGetQueryKey(hid),
    })
  }

  const handleVisibilityChange = (mode: VisibilityMode) => {
    if (mode !== household?.visibility_mode) {
      setPendingVisibility(mode)
    }
  }

  const confirmVisibilityChange = async () => {
    if (!pendingVisibility) return
    await updateHousehold.mutateAsync({
      householdId: hid,
      data: { visibility_mode: pendingVisibility },
    })
    setPendingVisibility(null)
    await qc.invalidateQueries({
      queryKey: getGetHouseholdApiV1HouseholdsHouseholdIdGetQueryKey(hid),
    })
  }

  const handleCurrencyChange = (code: string) => {
    if (code !== household?.home_currency) {
      setPendingCurrency(code)
    }
  }

  const confirmCurrencyChange = async () => {
    if (!pendingCurrency) return
    const result = await updateHousehold.mutateAsync({
      householdId: hid,
      data: { home_currency: pendingCurrency },
    })
    setPendingCurrency(null)
    await qc.invalidateQueries({
      queryKey: getGetHouseholdApiV1HouseholdsHouseholdIdGetQueryKey(hid),
    })
    if (result.recompute_started) {
      setRecomputing(true)
    }
  }

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return
    setInviteError(null)
    setInviteResult(null)
    try {
      const result = await createInvitation.mutateAsync({
        householdId: hid,
        data: { email: inviteEmail.trim(), role: inviteRole },
      })
      setInviteResult(result)
      setInviteEmail('')
      await qc.invalidateQueries({ queryKey: invitationsKey })
    } catch (err: unknown) {
      const status = (err as { status?: number }).status
      if (status === 409) {
        setInviteError('A pending invitation already exists for this email.')
      } else if (status === 422) {
        setInviteError('Invalid email address.')
      } else {
        setInviteError('Failed to send invitation. Try again.')
      }
    }
  }

  const handleResend = async (invitationId: string) => {
    await resendInvitation.mutateAsync({ householdId: hid, invitationId })
    await qc.invalidateQueries({ queryKey: invitationsKey })
  }

  const handleRevoke = async (invitationId: string) => {
    await revokeInvitation.mutateAsync({ householdId: hid, invitationId })
    await qc.invalidateQueries({ queryKey: invitationsKey })
  }

  const handleCopyLink = async (inviteUrl: string, invitationId: string) => {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopiedId(invitationId)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      // clipboard not available — silently ignore
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: '0 0 20px' }}>
        Household
      </h2>

      {recomputing && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 14px',
            marginBottom: 16,
            background: 'color-mix(in oklch, var(--accent) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--accent) 30%, transparent)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--fg-secondary)',
          }}
        >
          <RefreshCw size={13} className="animate-spin" style={{ flexShrink: 0 }} />
          Recalculating FX rates for all transactions, budgets, and goals...
        </div>
      )}

      {pendingCurrency && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '24px 28px',
              maxWidth: 400,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <AlertTriangle size={18} style={{ flexShrink: 0, color: '#f59e0b', marginTop: 1 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
                  Change home currency to {pendingCurrency}?
                </div>
                <div style={{ fontSize: 13, color: 'var(--fg-muted)', lineHeight: 1.5 }}>
                  This will re-trigger FX computation for all transactions, budgets, and goals.
                  Existing home-currency amounts will be overwritten.
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setPendingCurrency(null)}
                style={{
                  padding: '8px 16px',
                  fontSize: 13,
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-muted)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void confirmCurrencyChange()}
                disabled={updateHousehold.isPending}
                style={{
                  padding: '8px 16px',
                  fontSize: 13,
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  border: 'none',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 500,
                  opacity: updateHousehold.isPending ? 0.6 : 1,
                }}
              >
                {updateHousehold.isPending ? 'Saving...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingVisibility && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 50,
          }}
        >
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '24px 28px',
              maxWidth: 400,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <AlertTriangle size={18} style={{ flexShrink: 0, color: '#f59e0b', marginTop: 1 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
                  Change visibility mode?
                </div>
                <div style={{ fontSize: 13, color: 'var(--fg-muted)', lineHeight: 1.5 }}>
                  This affects what all household members can see. Switching modes may expose or
                  hide transactions for existing members.
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setPendingVisibility(null)}
                style={{
                  padding: '8px 16px',
                  fontSize: 13,
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-muted)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void confirmVisibilityChange()}
                disabled={updateHousehold.isPending}
                style={{
                  padding: '8px 16px',
                  fontSize: 13,
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  border: 'none',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 500,
                  opacity: updateHousehold.isPending ? 0.6 : 1,
                }}
              >
                {updateHousehold.isPending ? 'Saving...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      <SettingRow label="Household name">
        <InlineEdit value={household.name} onSave={handleSaveName} />
      </SettingRow>

      <SettingRow label="Home currency" description="All amounts are converted to this currency">
        <div style={{ width: 260 }}>
          <CurrencySelect
            value={household.home_currency}
            onChange={handleCurrencyChange}
            disabled={!isOwner}
          />
        </div>
      </SettingRow>

      <SettingRow label="Visibility mode" description="Controls who can view this household">
        <div style={{ display: 'flex', gap: 6 }}>
          {VISIBILITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              title={opt.description}
              onClick={() => handleVisibilityChange(opt.value as VisibilityMode)}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                borderRadius: 6,
                border: `1px solid ${household.visibility_mode === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                background:
                  household.visibility_mode === opt.value
                    ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                    : 'none',
                color:
                  household.visibility_mode === opt.value ? 'var(--accent)' : 'var(--fg-muted)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </SettingRow>

      <div
        style={{
          padding: '16px 0',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-primary)' }}>Members</div>
        {(members as MembershipOut[]).map((m) => (
          <div
            key={m.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 10,
            }}
          >
            <InitialsChip name={m.user.display_name} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                {m.user.display_name}
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{m.user.email}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  borderRadius: 99,
                  fontSize: 11,
                  fontWeight: 500,
                  background:
                    m.role === 'owner'
                      ? 'color-mix(in oklch, var(--accent) 15%, transparent)'
                      : 'var(--bg-secondary)',
                  color: m.role === 'owner' ? 'var(--accent)' : 'var(--fg-muted)',
                  border: `1px solid ${m.role === 'owner' ? 'color-mix(in oklch, var(--accent) 30%, transparent)' : 'var(--border)'}`,
                }}
              >
                {m.role === 'owner' && <Crown size={10} />}
                {m.role}
              </span>
              {isOwner && m.user_id !== me?.id && (
                <>
                  {confirmRemove === m.user_id ? (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        type="button"
                        onClick={() => void handleRemove(m.user_id)}
                        style={{
                          padding: '4px 10px',
                          fontSize: 11,
                          background: 'var(--danger)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmRemove(null)}
                        style={{
                          padding: '4px 10px',
                          fontSize: 11,
                          background: 'none',
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          cursor: 'pointer',
                          color: 'var(--fg-muted)',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmRemove(m.user_id)}
                      title="Remove member"
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--fg-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        padding: 4,
                      }}
                    >
                      <UserMinus size={14} />
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        ))}

        {isOwner && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
              Invite member
            </div>

            {/* SMTP not configured banner */}
            {smtpStatus && !smtpStatus.smtp_configured && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 12px',
                  background: 'color-mix(in oklch, var(--warning, #f59e0b) 10%, transparent)',
                  border: '1px solid color-mix(in oklch, var(--warning, #f59e0b) 30%, transparent)',
                  borderRadius: 8,
                  fontSize: 12,
                  color: 'var(--fg-secondary)',
                }}
              >
                <AlertTriangle size={13} style={{ flexShrink: 0, color: '#f59e0b' }} />
                SMTP not configured. Invitations will be created but email will not be sent. Copy
                the link manually.
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void handleInvite()
                }}
                placeholder="Email address"
                type="email"
                style={{
                  flex: 1,
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'member' | 'owner')}
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                <option value="member">Member</option>
                <option value="owner">Owner</option>
              </select>
              <button
                type="button"
                onClick={() => void handleInvite()}
                disabled={!inviteEmail.trim() || createInvitation.isPending}
                style={{
                  padding: '8px 16px',
                  background:
                    inviteEmail.trim() && !createInvitation.isPending
                      ? 'var(--accent)'
                      : 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 13,
                  color:
                    inviteEmail.trim() && !createInvitation.isPending
                      ? 'var(--accent-fg)'
                      : 'var(--fg-muted)',
                  cursor:
                    inviteEmail.trim() && !createInvitation.isPending ? 'pointer' : 'not-allowed',
                  fontFamily: 'var(--font-sans)',
                  whiteSpace: 'nowrap',
                }}
              >
                {createInvitation.isPending ? 'Sending...' : 'Invite'}
              </button>
            </div>

            {inviteError && (
              <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>{inviteError}</p>
            )}

            {/* Result card */}
            {inviteResult && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  background: inviteResult.email_sent
                    ? 'color-mix(in oklch, var(--success, #22c55e) 10%, transparent)'
                    : 'var(--bg-secondary)',
                  border: `1px solid ${inviteResult.email_sent ? 'color-mix(in oklch, var(--success, #22c55e) 30%, transparent)' : 'var(--border)'}`,
                  borderRadius: 8,
                }}
              >
                {inviteResult.email_sent ? (
                  <Mail size={14} style={{ marginTop: 1, flexShrink: 0, color: '#22c55e' }} />
                ) : (
                  <MailX
                    size={14}
                    style={{ marginTop: 1, flexShrink: 0, color: 'var(--fg-muted)' }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--fg-primary)', fontWeight: 500 }}>
                    {inviteResult.email_sent
                      ? `Invitation sent to ${inviteResult.invited_email}`
                      : `Invitation created (email not sent)`}
                  </div>
                  {!inviteResult.email_sent && (
                    <button
                      type="button"
                      onClick={() => void handleCopyLink(inviteResult.invite_url, inviteResult.id)}
                      style={{
                        marginTop: 4,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 11,
                        color: 'var(--accent)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        fontFamily: 'var(--font-sans)',
                      }}
                    >
                      <Copy size={10} />
                      {copiedId === inviteResult.id ? 'Copied!' : 'Copy invite link'}
                    </button>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setInviteResult(null)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--fg-muted)',
                    padding: 2,
                    lineHeight: 1,
                  }}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Pending invitations list */}
            {(invitations as InvitationOut[]).length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 2 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--fg-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Pending invitations
                </div>
                {(invitations as InvitationOut[]).map((inv) => (
                  <div
                    key={inv.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 12px',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          color: 'var(--fg-primary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {inv.invited_email}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 1 }}>
                        {inv.role} &middot; {inv.email_sent ? 'Email sent' : 'Email not sent'}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                      <button
                        type="button"
                        title="Copy invite link"
                        onClick={() => void handleCopyLink(inv.invite_url, inv.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--fg-muted)',
                          padding: 4,
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        {copiedId === inv.id ? (
                          <span style={{ fontSize: 10 }}>Copied</span>
                        ) : (
                          <Copy size={13} />
                        )}
                      </button>
                      <button
                        type="button"
                        title="Resend invitation"
                        onClick={() => void handleResend(inv.id)}
                        disabled={resendInvitation.isPending}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--fg-muted)',
                          padding: 4,
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        <RefreshCw size={13} />
                      </button>
                      <button
                        type="button"
                        title="Revoke invitation"
                        onClick={() => void handleRevoke(inv.id)}
                        disabled={revokeInvitation.isPending}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--danger)',
                          padding: 4,
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {!isOwner && (
        <div style={{ paddingTop: 20 }}>
          <button
            type="button"
            style={{
              padding: '8px 16px',
              background: 'none',
              border: '1px solid var(--danger)',
              borderRadius: 8,
              fontSize: 13,
              color: 'var(--danger)',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Leave household
          </button>
        </div>
      )}
    </div>
  )
}
