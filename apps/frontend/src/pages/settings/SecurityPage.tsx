import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

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

export function SecurityPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setError,
  } = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  const onSubmit = async (_: PasswordForm) => {
    try {
      await Promise.resolve()
      reset()
    } catch {
      setError('current_password', { message: 'Incorrect current password' })
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
              disabled={isSubmitting}
              style={{
                padding: '8px 18px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.7 : 1,
                fontFamily: 'var(--font-sans)',
              }}
            >
              {isSubmitting ? 'Updating...' : 'Update password'}
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
          gap: 12,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Active sessions
          </div>
          <span
            style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 99,
              background: 'var(--bg-secondary)',
              color: 'var(--fg-muted)',
              border: '1px solid var(--border)',
            }}
          >
            Coming soon
          </span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
          Session management will show all active login sessions and let you revoke them.
        </div>
      </div>
    </div>
  )
}
