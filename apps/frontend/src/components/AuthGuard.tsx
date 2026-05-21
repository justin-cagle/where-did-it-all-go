import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { customInstance, ApiError } from '@/api/client'

interface MeResponse {
  id: string
  email: string
  display_name: string
  is_app_admin: boolean
  totp_enabled: boolean
}

interface HouseholdOut {
  id: string
}

interface AuthGuardProps {
  children: ReactNode
  requireHousehold?: boolean
}

export function AuthGuard({ children, requireHousehold = true }: AuthGuardProps) {
  const { isLoading, isAuthenticated, setUser, clearUser, setLoading } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    customInstance<MeResponse>({ url: '/api/v1/auth/me', method: 'GET' })
      .then(async (user) => {
        if (cancelled) return
        setUser(user)

        if (!requireHousehold) return

        const households = await customInstance<HouseholdOut[]>({
          url: '/api/v1/households',
          method: 'GET',
        })

        if (!cancelled && households.length === 0) {
          navigate(user.is_app_admin ? '/admin' : '/waiting', { replace: true })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        clearUser()
        if (err instanceof ApiError && err.status === 401) {
          navigate('/login', { replace: true })
        }
      })

    return () => {
      cancelled = true
    }
  }, [setUser, clearUser, setLoading, navigate, requireHousehold])

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary)',
        }}
      >
        <Spinner />
      </div>
    )
  }

  if (!isAuthenticated) return null

  return <>{children}</>
}

function Spinner() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      style={{ animation: 'spin 0.8s linear infinite' }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <circle cx="16" cy="16" r="13" stroke="var(--border)" strokeWidth="2.5" />
      <path
        d="M16 3 A13 13 0 0 1 29 16"
        stroke="var(--accent)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  )
}
