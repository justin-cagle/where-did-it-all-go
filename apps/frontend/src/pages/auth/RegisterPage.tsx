import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { customInstance, ApiError } from '@/api/client'
import { AuthLayout } from './LoginPage'

function safeRedirect(raw: string | null): string | null {
  if (!raw) return null
  const decoded = decodeURIComponent(raw)
  if (decoded.startsWith('/invite/')) return decoded
  return null
}

interface RegistrationSettings {
  allow_registration: boolean
  registration_limit: number | null
  unassigned_account_ttl_days: number
}

interface RegisterApiResponse {
  user_id: string
  is_app_admin: boolean
  has_household: boolean
  redirect: string
}

const schema = z
  .object({
    display_name: z.string().min(1, 'Name is required').max(100),
    email: z.string().email('Enter a valid email'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type Fields = z.infer<typeof schema>

export function RegisterPage() {
  const { setUser } = useAuthStore()
  const navigate = useNavigate()
  const [settings, setSettings] = useState<RegistrationSettings | null>(null)

  const urlParams = new URLSearchParams(window.location.search)
  const inviteToken = urlParams.get('invite')
  const prefillEmail = urlParams.get('email') ?? ''
  const redirectAfter = safeRedirect(urlParams.get('redirect'))

  useEffect(() => {
    customInstance<RegistrationSettings>({
      url: '/api/v1/settings/registration',
      method: 'GET',
    })
      .then(setSettings)
      .catch(() => {
        // non-critical — default to showing the form
        setSettings({
          allow_registration: true,
          registration_limit: null,
          unassigned_account_ttl_days: 7,
        })
      })
  }, [])

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema), defaultValues: { email: prefillEmail } })

  const onSubmit = async (data: Fields) => {
    try {
      const result = await customInstance<RegisterApiResponse>({
        url: '/api/v1/auth/register',
        method: 'POST',
        data: {
          email: data.email,
          password: data.password,
          display_name: data.display_name,
        },
      })

      setUser({
        id: result.user_id,
        email: data.email,
        display_name: data.display_name,
        is_app_admin: result.is_app_admin,
        totp_enabled: false,
        avatar_url: null,
      })
      navigate(redirectAfter ?? result.redirect, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('email', { message: 'Email already registered' })
      } else if (err instanceof ApiError && err.status === 403) {
        const type = (err.problem['type'] as string | undefined) ?? ''
        if (type === 'registration_limit_reached') {
          setError('root', { message: 'Registration is full. Contact your administrator.' })
        } else {
          setError('root', { message: 'Registration is closed. Contact your administrator.' })
        }
      } else if (err instanceof ApiError && err.status === 422) {
        setError('root', { message: 'Check your inputs and try again.' })
      } else {
        setError('root', { message: 'Something went wrong. Try again.' })
      }
    }
  }

  // Show closed state when: settings loaded, registration closed, and no invite token in URL
  const registrationClosed = settings !== null && !settings.allow_registration && !inviteToken

  if (registrationClosed) {
    return (
      <AuthLayout>
        <h1 style={heading}>Registration closed</h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', lineHeight: 1.6, margin: 0 }}>
          Registration is closed. Contact your administrator or use an invitation link to create an
          account.
        </p>
        <p style={footer}>
          <Link to="/login" style={link}>
            Back to login
          </Link>
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 style={heading}>Create account</h1>

      <form onSubmit={handleSubmit(onSubmit)} noValidate style={form}>
        <Field label="Display name" error={errors.display_name?.message}>
          <input
            {...register('display_name')}
            type="text"
            autoComplete="name"
            style={inputStyle(!!errors.display_name)}
            placeholder="Jane Smith"
          />
        </Field>

        <Field label="Email" error={errors.email?.message}>
          <input
            {...register('email')}
            type="email"
            autoComplete="email"
            readOnly={!!prefillEmail}
            style={{
              ...inputStyle(!!errors.email),
              ...(prefillEmail
                ? { background: 'var(--bg-secondary)', color: 'var(--fg-muted)' }
                : {}),
            }}
            placeholder="you@example.com"
          />
        </Field>

        <Field label="Password" error={errors.password?.message}>
          <input
            {...register('password')}
            type="password"
            autoComplete="new-password"
            style={inputStyle(!!errors.password)}
            placeholder="At least 8 characters"
          />
        </Field>

        <Field label="Confirm password" error={errors.confirm_password?.message}>
          <input
            {...register('confirm_password')}
            type="password"
            autoComplete="new-password"
            style={inputStyle(!!errors.confirm_password)}
            placeholder="••••••••"
          />
        </Field>

        {settings?.allow_registration && settings.registration_limit !== null && (
          <p style={{ fontSize: 12, color: 'var(--fg-muted)', margin: 0 }}>Registration is open.</p>
        )}

        {errors.root && (
          <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{errors.root.message}</p>
        )}

        <button type="submit" disabled={isSubmitting} style={submitButton}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>

      <p style={footer}>
        Already have an account?{' '}
        <Link to="/login" style={link}>
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}

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

const heading: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 600,
  color: 'var(--fg-primary)',
  margin: 0,
}
const form: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 16 }
const submitButton: React.CSSProperties = {
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
}
const footer: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--fg-muted)',
  textAlign: 'center',
  margin: 0,
}
const link: React.CSSProperties = { color: 'var(--accent)', textDecoration: 'none' }
