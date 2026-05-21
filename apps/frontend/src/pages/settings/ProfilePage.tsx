import { useState } from 'react'
import {
  useMeApiV1AuthMeGet,
  useUpdateMeApiV1AuthMePatch,
  getMeApiV1AuthMeGetQueryKey,
} from '@/api/generated/households/households'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/store'

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

  const handleCancel = () => {
    setDraft(value)
    setEditing(false)
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
        onClick={handleCancel}
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

export function ProfilePage() {
  const qc = useQueryClient()
  const { data: me, isLoading } = useMeApiV1AuthMeGet()
  const updateMe = useUpdateMeApiV1AuthMePatch()
  const { currentUser, setUser } = useAuthStore()

  if (isLoading) {
    return <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  if (!me) return null

  const handleSaveName = async (display_name: string) => {
    await updateMe.mutateAsync({ data: { display_name } })
    await qc.invalidateQueries({ queryKey: getMeApiV1AuthMeGetQueryKey() })
    if (currentUser) {
      setUser({ ...currentUser, display_name })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: '0 0 20px' }}>
        Profile
      </h2>

      <SettingRow label="Display name" description="Shown to other household members">
        <InlineEdit value={me.display_name} onSave={handleSaveName} />
      </SettingRow>

      <SettingRow label="Email" description="Sign-in email address (cannot be changed)">
        <span style={{ fontSize: 14, color: 'var(--fg-muted)' }}>{me.email}</span>
      </SettingRow>

      <SettingRow
        label="Two-factor authentication"
        description={
          me.totp_enabled
            ? 'TOTP is enabled. Disable to stop requiring a code on sign-in.'
            : 'Enable TOTP for additional sign-in security.'
        }
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              fontSize: 12,
              padding: '2px 8px',
              borderRadius: 99,
              background: me.totp_enabled
                ? 'color-mix(in oklch, var(--success) 15%, transparent)'
                : 'var(--bg-secondary)',
              color: me.totp_enabled ? 'var(--success)' : 'var(--fg-muted)',
              border: `1px solid ${me.totp_enabled ? 'color-mix(in oklch, var(--success) 30%, transparent)' : 'var(--border)'}`,
            }}
          >
            {me.totp_enabled ? 'Enabled' : 'Disabled'}
          </span>
          <button
            type="button"
            style={{
              fontSize: 12,
              color: me.totp_enabled ? 'var(--danger)' : 'var(--accent)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              fontFamily: 'var(--font-sans)',
            }}
          >
            {me.totp_enabled ? 'Disable' : 'Enable'}
          </button>
        </div>
      </SettingRow>
    </div>
  )
}
