import { useState } from 'react'
import { UserMinus, Crown } from 'lucide-react'
import {
  useGetHouseholdApiV1HouseholdsHouseholdIdGet,
  useListMembersApiV1HouseholdsHouseholdIdMembersGet,
  useRemoveMemberApiV1HouseholdsHouseholdIdMembersUserIdDelete,
  useMeApiV1AuthMeGet,
} from '@/api/generated/households/households'
import { useHousehold } from '@/hooks/use-household'
import { useQueryClient } from '@tanstack/react-query'
import type { MembershipOut } from '@/api/generated/model/membershipOut'

const VISIBILITY_OPTIONS = [
  {
    value: 'private',
    label: 'Private',
    description: 'Only members can see this household',
  },
  {
    value: 'shared',
    label: 'Shared',
    description: 'Visible to invited collaborators',
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

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(draft)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 14, color: 'var(--fg-primary)' }}>{value}</span>
        <button
          type="button"
          onClick={() => {
            setDraft(value)
            setEditing(true)
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        autoFocus
        style={{
          padding: '6px 10px',
          borderRadius: 8,
          border: '1px solid var(--border)',
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
        onClick={() => setEditing(false)}
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
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)

  const { data: household } = useGetHouseholdApiV1HouseholdsHouseholdIdGet(hid, {
    query: { enabled: !!hid },
  })
  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(hid, {
    query: { enabled: !!hid },
  })
  const { data: me } = useMeApiV1AuthMeGet()
  const removeMember = useRemoveMemberApiV1HouseholdsHouseholdIdMembersUserIdDelete()

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

  const handleSaveName = async (_: string) => {
    await Promise.resolve()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: '0 0 20px' }}>
        Household
      </h2>

      <SettingRow label="Household name">
        <InlineEdit value={household.name} onSave={handleSaveName} />
      </SettingRow>

      <SettingRow label="Visibility mode" description="Controls who can view this household">
        <div style={{ display: 'flex', gap: 6 }}>
          {VISIBILITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              title={opt.description}
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
            Invite member
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
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
            <button
              type="button"
              title="Coming soon"
              style={{
                padding: '8px 16px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--fg-muted)',
                cursor: 'default',
                fontFamily: 'var(--font-sans)',
              }}
            >
              Invite (coming soon)
            </button>
          </div>
        </div>
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
