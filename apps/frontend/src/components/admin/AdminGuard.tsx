import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'

interface AdminGuardProps {
  children: ReactNode
}

export function AdminGuard({ children }: AdminGuardProps) {
  const navigate = useNavigate()
  const { isLoading, isAuthenticated, currentUser } = useAuthStore()

  useEffect(() => {
    if (!isLoading && (!isAuthenticated || !currentUser?.is_app_admin)) {
      navigate('/dashboard', { replace: true })
    }
  }, [isLoading, isAuthenticated, currentUser, navigate])

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0a0f1a',
        }}
      >
        <AdminSpinner />
      </div>
    )
  }

  if (!isAuthenticated || !currentUser?.is_app_admin) return null

  return <>{children}</>
}

function AdminSpinner() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      style={{ animation: 'spin 0.8s linear infinite' }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <circle cx="16" cy="16" r="13" stroke="#1f2937" strokeWidth="2.5" />
      <path d="M16 3 A13 13 0 0 1 29 16" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}
