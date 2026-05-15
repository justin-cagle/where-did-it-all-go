import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { customInstance, ApiError } from '@/api/client'
import { AuthLayout } from './LoginPage'

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

interface RegisterResponse {
  id: string
  email: string
  display_name: string
  is_app_admin: boolean
  totp_required: boolean
}

export function RegisterPage() {
  const { setUser } = useAuthStore()
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: Fields) => {
    try {
      const result = await customInstance<RegisterResponse>({
        url: '/api/v1/auth/register',
        method: 'POST',
        data: {
          email: data.email,
          password: data.password,
          display_name: data.display_name,
        },
      })

      if (result.totp_required) {
        navigate('/register/totp-setup', { replace: true })
      } else {
        setUser(result)
        navigate('/onboarding', { replace: true })
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('email', { message: 'Email already registered' })
      } else if (err instanceof ApiError && err.status === 422) {
        setError('root', { message: 'Check your inputs and try again.' })
      } else {
        setError('root', { message: 'Something went wrong. Try again.' })
      }
    }
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
            style={inputStyle(!!errors.email)}
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
