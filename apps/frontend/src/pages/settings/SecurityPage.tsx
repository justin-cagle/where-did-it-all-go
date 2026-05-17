import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  useListSessionsApiV1AuthSessionsGet,
  useChangePasswordApiV1AuthChangePasswordPost,
  getListSessionsApiV1AuthSessionsGetQueryKey,
} from '@/api/generated/households/households'
import { useQueryClient } from '@tanstack/react-query'
import { customInstance, ApiError } from '@/api/client'

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    new_password: z.string().min(8, 'Minimum 8 characters'),
    confirm_password: z.string().min(1, 'Required'),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type PasswordForm = z.infer<typeof passwordSchema>

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 3 }}>{message}</div>
}

function relativeTime(iso: string): string {
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const diffSec = Math.floor(diffMs / 1000)
    if (diffSec < 60) return 'just now'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? 's' : ''} ago`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 30) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`
    const diffMo = Math.floor(diffDay / 30)
    return `${diffMo} month${diffMo !== 1 ? 's' : ''} ago`
  } catch {
    return iso
  }
}

function truncate(s: string | null | undefined, max: number): string {
  if (!s) return 'Unknown device'
  return s.length > max ? s.slice(0, max) + '...' : s
}

function SessionsList() {
  const qc = useQueryClient()
  const { data: sessions, isLoading } = useListSessionsApiV1AuthSessionsGet({
    query: { staleTime: 0 },
  })

  const sorted = sessions
    ? [...sessions].sort(
        (a, b) => new Date(b.last_used_at).getTime() - new Date(a.last_used_at).getTime()
      )
    : []

  async function revokeSession(id: string) {
    await customInstance({ url: `/api/v1/auth/sessions/${id}`, method: 'DELETE' })
    await qc.invalidateQueries({ queryKey: getListSessionsApiV1AuthSessionsGetQueryKey() })
  }

  if (isLoading) {
    return (
      <div style={{ padding: '16px 0', fontSize: 13, color: 'var(--fg-muted)' }}>
        Loading sessions...
      </div>
    )
  }

  if (!sorted.length) {
    return <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>No active sessions found.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {sorted.map((session, idx) => {
        const isCurrent = idx === 0
        return (
          <div
            key={session.id}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 12,
              padding: '10px 12px',
              borderRadius: 8,
              background: isCurrent
                ? 'color-mix(in oklch, var(--accent) 6%, transparent)'
                : 'var(--bg-secondary)',
              border: isCurrent
                ? '1px solid color-mix(in oklch, var(--accent) 30%, transparent)'
                : '1px solid var(--border)',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--fg-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {truncate(session.user_agent, 60)}
                {isCurrent && (
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: 10,
                      fontWeight: 600,
                      color: 'var(--accent)',
                      background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
                      borderRadius: 4,
                      padding: '1px 5px',
                    }}
                  >
                    current
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
                Created {relativeTime(session.created_at)} &middot; Last used{' '}
                {relativeTime(session.last_used_at)}
              </div>
            </div>
            {!isCurrent && (
              <button
                type="button"
                onClick={() => void revokeSession(session.id)}
                style={{
                  flexShrink: 0,
                  fontSize: 12,
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: '1px solid color-mix(in oklch, var(--danger) 40%, transparent)',
                  background: 'transparent',
                  color: 'var(--danger)',
                  cursor: 'pointer',
                }}
              >
                Revoke
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function SecurityPage() {
  const qc = useQueryClient()
  const changePassword = useChangePasswordApiV1AuthChangePasswordPost()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setError,
  } = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  const onSubmit = async (data: PasswordForm) => {
    try {
      await changePassword.mutateAsync({
        data: {
          current_password: data.current_password,
          new_password: data.new_password,
        },
      })
      reset()
      await qc.invalidateQueries({ queryKey: getListSessionsApiV1AuthSessionsGetQueryKey() })
    } catch (err: unknown) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 401)) {
        setError('current_password', { message: 'Current password is incorrect' })
      } else {
        setError('current_password', { message: 'Update failed. Try again.' })
      }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 480 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
        Security
      </h2>

      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
          Change password
        </div>

        <form
          onSubmit={(e) => void handleSubmit(onSubmit)(e)}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Current password</label>
            <input
              type="password"
              {...register('current_password')}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: `1px solid ${errors.current_password ? 'var(--danger)' : 'var(--border)'}`,
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
            <FieldError message={errors.current_password?.message} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>New password</label>
            <input
              type="password"
              {...register('new_password')}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: `1px solid ${errors.new_password ? 'var(--danger)' : 'var(--border)'}`,
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
            <FieldError message={errors.new_password?.message} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Confirm new password</label>
            <input
              type="password"
              {...register('confirm_password')}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: `1px solid ${errors.confirm_password ? 'var(--danger)' : 'var(--border)'}`,
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
            <FieldError message={errors.confirm_password?.message} />
          </div>

          <div style={{ paddingTop: 4 }}>
            <button
              type="submit"
              disabled={isSubmitting || changePassword.isPending}
              style={{
                padding: '8px 18px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                cursor: isSubmitting || changePassword.isPending ? 'not-allowed' : 'pointer',
                opacity: isSubmitting || changePassword.isPending ? 0.7 : 1,
                fontFamily: 'var(--font-sans)',
              }}
            >
              {isSubmitting || changePassword.isPending ? 'Updating...' : 'Update password'}
            </button>
          </div>
        </form>
      </div>

      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
          Active sessions
        </div>
        <SessionsList />
      </div>
    </div>
  )
}
