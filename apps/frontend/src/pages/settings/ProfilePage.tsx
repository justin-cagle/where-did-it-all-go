import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useMeApiV1AuthMeGet,
  useUpdateMeApiV1AuthMePatch,
  useTotpDisableApiV1AuthTotpDisableDelete,
  getMeApiV1AuthMeGetQueryKey,
} from '@/api/generated/households/households'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/store'

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

  const handleCancel = () => {
    setDraft(value)
    setEditing(false)
    setSaveError(null)
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
      {saveError && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{saveError}</div>}
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

function AvatarSection({
  avatarUrl,
  displayName,
  onSave,
}: {
  avatarUrl: string | null
  displayName: string
  onSave: (url: string | null) => Promise<void>
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const initials = displayName
    .split(' ')
    .map((p) => p[0] ?? '')
    .slice(0, 2)
    .join('')
    .toUpperCase()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 512 * 1024) {
      setError('Image must be under 512 KB')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      await onSave(dataUrl)
    } catch {
      setError('Failed to save avatar')
    } finally {
      setSaving(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const handleRemove = async () => {
    setSaving(true)
    setError(null)
    try {
      await onSave(null)
    } catch {
      setError('Failed to remove avatar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: '50%',
          overflow: 'hidden',
          background: 'var(--accent)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          border: '2px solid var(--border)',
        }}
      >
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt="Avatar"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ color: 'var(--accent-fg)', fontSize: 18, fontWeight: 600 }}>
            {initials}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            style={{ display: 'none' }}
            onChange={(e) => void handleFileChange(e)}
          />
          <button
            type="button"
            disabled={saving}
            onClick={() => fileRef.current?.click()}
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
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? 'Saving...' : 'Upload photo'}
          </button>
          {avatarUrl && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleRemove()}
              style={{
                padding: '6px 14px',
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--danger)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              Remove
            </button>
          )}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
          PNG, JPG, WebP or GIF. Max 512 KB.
        </div>
        {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}
      </div>
    </div>
  )
}

export function ProfilePage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data: me, isLoading } = useMeApiV1AuthMeGet()
  const updateMe = useUpdateMeApiV1AuthMePatch()
  const disableTotp = useTotpDisableApiV1AuthTotpDisableDelete()
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

  const handleSaveAvatar = async (avatar_url: string | null) => {
    await updateMe.mutateAsync({ data: { display_name: me.display_name, avatar_url } })
    await qc.invalidateQueries({ queryKey: getMeApiV1AuthMeGetQueryKey() })
    if (currentUser) {
      setUser({ ...currentUser, avatar_url })
    }
  }

  const handleEnableTotp = () => {
    navigate('/settings/totp-setup', { state: { returnTo: '/settings/profile' } })
  }

  const handleDisableTotp = async () => {
    await disableTotp.mutateAsync()
    await qc.invalidateQueries({ queryKey: getMeApiV1AuthMeGetQueryKey() })
    if (currentUser) {
      setUser({ ...currentUser, totp_enabled: false })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: '0 0 20px' }}>
        Profile
      </h2>

      <SettingRow label="Avatar" description="Photo shown in the top bar and to household members">
        <AvatarSection
          avatarUrl={me.avatar_url ?? null}
          displayName={me.display_name}
          onSave={handleSaveAvatar}
        />
      </SettingRow>

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
            disabled={disableTotp.isPending}
            onClick={me.totp_enabled ? () => void handleDisableTotp() : handleEnableTotp}
            style={{
              fontSize: 12,
              color: me.totp_enabled ? 'var(--danger)' : 'var(--accent)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              fontFamily: 'var(--font-sans)',
              opacity: disableTotp.isPending ? 0.6 : 1,
            }}
          >
            {disableTotp.isPending ? 'Disabling...' : me.totp_enabled ? 'Disable' : 'Enable'}
          </button>
        </div>
      </SettingRow>
    </div>
  )
}
