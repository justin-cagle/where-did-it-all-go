import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { customInstance, ApiError } from '@/api/client'

interface InstanceInfo {
  aio_mode: boolean
  version: string
  demo_credentials: { email: string; password: string } | null
}

async function fetchInstanceInfo(): Promise<InstanceInfo | null> {
  try {
    return await customInstance<InstanceInfo>({
      url: '/api/v1/settings/instance-info',
      method: 'GET',
    })
  } catch {
    return null
  }
}

function safeRedirect(raw: string | null): string {
  if (!raw) return '/'
  const decoded = decodeURIComponent(raw)
  if (decoded === '/dashboard' || decoded.startsWith('/invite/')) return decoded
  return '/'
}

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

const totpSchema = z.object({
  code: z.string().length(6, 'Enter the 6-digit code').regex(/^\d+$/, 'Digits only'),
})

type Fields = z.infer<typeof schema>
type TotpFields = z.infer<typeof totpSchema>

interface LoginResponse {
  id: string
  email: string
  display_name: string
  is_app_admin: boolean
  totp_enabled: boolean
}

export function LoginPage() {
  const { setUser } = useAuthStore()
  const navigate = useNavigate()
  const redirectTo = safeRedirect(new URLSearchParams(window.location.search).get('redirect'))
  const [instanceInfo, setInstanceInfo] = useState<InstanceInfo | null>(null)
  const [pendingCreds, setPendingCreds] = useState<{ email: string; password: string } | null>(null)

  useEffect(() => {
    fetchInstanceInfo().then(setInstanceInfo)
  }, [])

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) })

  const {
    register: registerTotp,
    handleSubmit: handleSubmitTotp,
    setError: setTotpError,
    formState: { errors: totpErrors, isSubmitting: totpSubmitting },
  } = useForm<TotpFields>({ resolver: zodResolver(totpSchema) })

  useEffect(() => {
    if (instanceInfo?.aio_mode && instanceInfo.demo_credentials) {
      setValue('email', instanceInfo.demo_credentials.email)
    }
  }, [instanceInfo, setValue])

  const doLogin = async (email: string, password: string, totp_code?: string) => {
    const user = await customInstance<LoginResponse>({
      url: '/api/v1/auth/login',
      method: 'POST',
      data: { email, password, totp_code: totp_code ?? null },
    })
    setUser(user)
    navigate(redirectTo, { replace: true })
  }

  const onSubmit = async (data: Fields) => {
    try {
      await doLogin(data.email, data.password)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (err.message === 'totp_required') {
          setPendingCreds({ email: data.email, password: data.password })
        } else {
          setError('root', { message: 'Invalid email or password' })
        }
      } else {
        setError('root', { message: 'Something went wrong. Try again.' })
      }
    }
  }

  const onTotpSubmit = async (data: TotpFields) => {
    if (!pendingCreds) return
    try {
      await doLogin(pendingCreds.email, pendingCreds.password, data.code)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setTotpError('code', { message: 'Invalid code. Try again.' })
      } else {
        setTotpError('root', { message: 'Something went wrong. Try again.' })
      }
    }
  }

  if (pendingCreds) {
    return (
      <AuthLayout demoBanner={null}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h1 style={styles.heading}>Two-factor authentication</h1>
          <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
            Enter the 6-digit code from your authenticator app.
          </p>
        </div>

        <form
          onSubmit={handleSubmitTotp(onTotpSubmit)}
          noValidate
          autoComplete="off"
          style={styles.form}
        >
          <Field label="Verification code" error={totpErrors.code?.message}>
            <input
              {...registerTotp('code')}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              maxLength={6}
              placeholder="000000"
              style={{
                ...inputStyle(!!totpErrors.code),
                fontSize: 24,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.3em',
                textAlign: 'center',
                height: 48,
              }}
            />
          </Field>

          {totpErrors.root && (
            <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>
              {totpErrors.root.message}
            </p>
          )}

          <button type="submit" disabled={totpSubmitting} style={styles.submitButton}>
            {totpSubmitting ? 'Verifying...' : 'Verify'}
          </button>
        </form>

        <p style={styles.footer}>
          <button
            type="button"
            onClick={() => setPendingCreds(null)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontSize: 13,
              fontFamily: 'var(--font-sans)',
              padding: 0,
            }}
          >
            Back to sign in
          </button>
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout demoBanner={instanceInfo?.aio_mode ? instanceInfo.demo_credentials : null}>
      <h1 style={styles.heading}>Sign in</h1>

      <form onSubmit={handleSubmit(onSubmit)} noValidate style={styles.form}>
        <Field label="Email" error={errors.email?.message}>
          <input
            {...register('email')}
            type="email"
            autoComplete="email"
            style={inputStyle(!!errors.email)}
            placeholder="you@example.com"
          />
        </Field>

        <Field label="Password" error={errors.password?.message}>
          <input
            {...register('password')}
            type="password"
            autoComplete="current-password"
            style={inputStyle(!!errors.password)}
            placeholder="••••••••"
          />
        </Field>

        {errors.root && (
          <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{errors.root.message}</p>
        )}

        <button type="submit" disabled={isSubmitting} style={styles.submitButton}>
          {isSubmitting ? 'Signing in...' : 'Sign in'}
        </button>
      </form>

      <p style={styles.footer}>
        No account?{' '}
        <Link to="/register" style={styles.link}>
          Register
        </Link>
      </p>
    </AuthLayout>
  )
}

/* ── Shared auth page layout ── */

export function AuthLayout({
  children,
  demoBanner,
}: {
  children: React.ReactNode
  demoBanner?: { email: string; password: string } | null
}) {
  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'var(--bg-primary)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 380,
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              style={{
                color: 'var(--accent-fg)',
                fontFamily: 'var(--font-mono)',
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              $
            </span>
          </div>
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--fg-primary)',
            }}
          >
            wdiag
          </span>
        </div>

        {/* Demo mode banner */}
        {demoBanner && (
          <div
            style={{
              background: 'var(--warning-bg, #fffbeb)',
              border: '1px solid var(--warning-border, #fcd34d)',
              borderRadius: 10,
              padding: '12px 14px',
              fontSize: 13,
              color: 'var(--warning-fg, #92400e)',
              lineHeight: 1.5,
            }}
          >
            <strong>Demo mode</strong>
            <br />
            Default credentials: {demoBanner.email} / {demoBanner.password}
            <br />
            Change them in Settings &rsaquo; Profile after login.
          </div>
        )}

        {/* Card */}
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 16,
            padding: '28px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            boxShadow: 'var(--shadow)',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

/* ── Field wrapper ── */

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>{label}</label>
      {children}
      {error && <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>{error}</p>}
    </div>
  )
}

function inputStyle(hasError: boolean): React.CSSProperties {
  return {
    height: 40,
    padding: '0 12px',
    borderRadius: 8,
    border: `1px solid ${hasError ? 'var(--danger)' : 'var(--border)'}`,
    background: 'var(--bg-primary)',
    color: 'var(--fg-primary)',
    fontSize: 14,
    fontFamily: 'var(--font-sans)',
    outline: 'none',
    width: '100%',
  }
}

const styles = {
  heading: {
    fontSize: 20,
    fontWeight: 600,
    color: 'var(--fg-primary)',
    margin: 0,
  } as React.CSSProperties,
  form: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 16,
  },
  submitButton: {
    height: 40,
    borderRadius: 8,
    border: 'none',
    background: 'var(--accent)',
    color: 'var(--accent-fg)',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'var(--font-sans)',
    marginTop: 4,
    opacity: 1,
    transition: 'opacity 0.1s',
  } as React.CSSProperties,
  footer: {
    fontSize: 13,
    color: 'var(--fg-muted)',
    textAlign: 'center' as const,
    margin: 0,
  } as React.CSSProperties,
  link: {
    color: 'var(--accent)',
    textDecoration: 'none',
  } as React.CSSProperties,
}
