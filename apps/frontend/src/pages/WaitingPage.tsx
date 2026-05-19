import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock } from 'lucide-react'
import { customInstance } from '@/api/client'
import { useAuthStore } from '@/store'

interface RegistrationSettings {
  allow_registration: boolean
  registration_limit: number | null
  unassigned_account_ttl_days: number
}

export function WaitingPage() {
  const navigate = useNavigate()
  const { clearUser, currentUser } = useAuthStore()
  const [ttlDays, setTtlDays] = useState<number | null>(null)

  // Admins with no household go to /admin, not /waiting
  useEffect(() => {
    if (currentUser?.is_app_admin) {
      navigate('/admin', { replace: true })
    }
  }, [currentUser, navigate])

  useEffect(() => {
    customInstance<RegistrationSettings>({
      url: '/api/v1/settings/registration',
      method: 'GET',
    })
      .then((s) => {
        if (s.unassigned_account_ttl_days > 0) {
          setTtlDays(s.unassigned_account_ttl_days)
        }
      })
      .catch(() => {
        // non-critical — page renders without TTL note
      })
  }, [])

  useEffect(() => {
    const source = new EventSource('/api/v1/households/events', {
      withCredentials: true,
    })

    source.addEventListener('household_assigned', () => {
      source.close()
      navigate('/onboarding', { replace: true })
    })

    source.onerror = () => {
      // SSE reconnects automatically; no action needed
    }

    return () => {
      source.close()
    }
  }, [navigate])

  const handleLogout = async () => {
    await customInstance({ url: '/api/v1/auth/logout', method: 'POST' }).catch(() => {})
    clearUser()
    navigate('/login', { replace: true })
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={iconWrap}>
          <Clock size={40} color="var(--fg-muted)" strokeWidth={1.5} />
        </div>

        <h1 style={headingStyle}>Waiting for access</h1>

        <p style={bodyStyle}>
          Your account has been created. A WDIAG administrator will assign you to a household.
          You'll be notified when access is granted.
        </p>

        {ttlDays !== null && (
          <p style={muteStyle}>
            Unassigned accounts are automatically removed after {ttlDays} day
            {ttlDays !== 1 ? 's' : ''}.
          </p>
        )}

        <button onClick={() => void handleLogout()} style={logoutButton}>
          Log out
        </button>
      </div>
    </div>
  )
}

const pageStyle: React.CSSProperties = {
  minHeight: '100dvh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg-primary)',
  padding: '24px 16px',
}

const cardStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 16,
  maxWidth: 420,
  width: '100%',
  textAlign: 'center',
}

const iconWrap: React.CSSProperties = {
  width: 72,
  height: 72,
  borderRadius: '50%',
  background: 'var(--bg-secondary)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 8,
}

const headingStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 600,
  color: 'var(--fg-primary)',
  margin: 0,
}

const bodyStyle: React.CSSProperties = {
  fontSize: 15,
  color: 'var(--fg-secondary)',
  lineHeight: 1.6,
  margin: 0,
}

const muteStyle: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--fg-muted)',
  margin: 0,
}

const logoutButton: React.CSSProperties = {
  marginTop: 8,
  height: 38,
  padding: '0 20px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--fg-secondary)',
  fontSize: 14,
  fontWeight: 500,
  cursor: 'pointer',
  fontFamily: 'var(--font-sans)',
}
