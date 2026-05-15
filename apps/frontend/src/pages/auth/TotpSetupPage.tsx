import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { customInstance, ApiError } from '@/api/client'
import { AuthLayout } from './LoginPage'

const schema = z.object({
  code: z.string().length(6, 'Enter the 6-digit code').regex(/^\d+$/, 'Digits only'),
})
type Fields = z.infer<typeof schema>

interface SetupResponse {
  qr_code_url: string
  secret: string
}

interface ConfirmResponse {
  id: string
  email: string
  display_name: string
  is_app_admin: boolean
}

export function TotpSetupPage() {
  const { setUser } = useAuthStore()
  const navigate = useNavigate()
  const [setup, setSetup] = useState<SetupResponse | null>(null)
  const [loadError, setLoadError] = useState('')

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) })

  useEffect(() => {
    customInstance<SetupResponse>({ url: '/api/v1/auth/totp/setup', method: 'GET' })
      .then(setSetup)
      .catch(() => setLoadError('Failed to load QR code. Reload to retry.'))
  }, [])

  const onSubmit = async (data: Fields) => {
    try {
      const user = await customInstance<ConfirmResponse>({
        url: '/api/v1/auth/totp/confirm',
        method: 'POST',
        data: { code: data.code },
      })
      setUser(user)
      navigate('/onboarding', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setError('code', { message: 'Invalid code. Try again.' })
      } else {
        setError('root', { message: 'Something went wrong. Try again.' })
      }
    }
  }

  return (
    <AuthLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Set up two-factor auth
        </h1>
        <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
          Scan this QR code with your authenticator app, then enter the 6-digit code.
        </p>
      </div>

      {loadError && <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{loadError}</p>}

      {/* QR code */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          padding: 20,
          background: 'var(--bg-secondary)',
          borderRadius: 12,
          border: '1px solid var(--border)',
        }}
      >
        {setup ? (
          <img
            src={setup.qr_code_url}
            alt="TOTP QR code"
            width={160}
            height={160}
            style={{ display: 'block' }}
          />
        ) : !loadError ? (
          <div
            style={{
              width: 160,
              height: 160,
              background: 'var(--border)',
              borderRadius: 8,
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          />
        ) : null}
      </div>

      {setup && (
        <p
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            margin: 0,
            wordBreak: 'break-all',
            textAlign: 'center',
          }}
        >
          Manual key: <span style={{ fontFamily: 'var(--font-mono)' }}>{setup.secret}</span>
        </p>
      )}

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>
            Verification code
          </label>
          <input
            {...register('code')}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            style={{
              height: 48,
              padding: '0 16px',
              borderRadius: 8,
              border: `1px solid ${errors.code ? 'var(--danger)' : 'var(--border)'}`,
              background: 'var(--bg-primary)',
              color: 'var(--fg-primary)',
              fontSize: 24,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.3em',
              textAlign: 'center',
              outline: 'none',
              width: '100%',
            }}
          />
          {errors.code && (
            <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>{errors.code.message}</p>
          )}
        </div>

        {errors.root && (
          <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{errors.root.message}</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !setup}
          style={{
            height: 40,
            borderRadius: 8,
            border: 'none',
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
            opacity: isSubmitting || !setup ? 0.6 : 1,
          }}
        >
          {isSubmitting ? 'Verifying...' : 'Verify and continue'}
        </button>
      </form>
    </AuthLayout>
  )
}
