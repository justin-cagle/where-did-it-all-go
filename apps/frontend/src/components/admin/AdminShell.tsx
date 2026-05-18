import type { ReactNode } from 'react'
import { useState, useEffect } from 'react'
import { NavLink, Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { customInstance } from '@/api/client'
import { useGetOverviewApiV1AdminOverviewGet } from '@/api/generated/admin/admin'

const A = {
  bg: '#0a0f1a',
  bgRaised: '#111827',
  sidebar: '#080d18',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
  danger: '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
}

function LayoutGridIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  )
}
function UsersIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
function HomeIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  )
}
function ServerIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="2" width="20" height="8" rx="2" />
      <rect x="2" y="14" width="20" height="8" rx="2" />
      <line x1="6" y1="6" x2="6.01" y2="6" />
      <line x1="6" y1="18" x2="6.01" y2="18" />
    </svg>
  )
}
function MailIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  )
}
function ArchiveIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <line x1="10" y1="12" x2="14" y2="12" />
    </svg>
  )
}
function AlertTriangleIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}
function LogOutIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  )
}
function ArrowLeftIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  )
}

const NAV = [
  { to: '/admin', label: 'Overview', icon: LayoutGridIcon, end: true },
  { to: '/admin/users', label: 'Users', icon: UsersIcon, end: false },
  { to: '/admin/households', label: 'Households', icon: HomeIcon, end: false },
  { to: '/admin/system', label: 'System', icon: ServerIcon, end: false },
  { to: '/admin/smtp', label: 'SMTP', icon: MailIcon, end: false },
  { to: '/admin/backup', label: 'Backup', icon: ArchiveIcon, end: false },
]

interface AdminShellProps {
  children: ReactNode
}

export function AdminShell({ children }: AdminShellProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          background: A.bg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          textAlign: 'center',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 320 }}>
          <AlertTriangleIcon />
          <div style={{ fontSize: 16, fontWeight: 600, color: A.fg }}>Desktop only</div>
          <div style={{ fontSize: 13, color: A.fgMuted }}>
            The admin panel is only available on desktop screens.
          </div>
          <Link
            to="/dashboard"
            style={{
              marginTop: 8,
              fontSize: 13,
              color: A.accent,
              textDecoration: 'none',
            }}
          >
            Back to app
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100dvh', background: A.bg, overflow: 'hidden' }}>
      <AdminSidebar />
      <div
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'auto' }}
      >
        {children}
      </div>
    </div>
  )
}

function AdminSidebar() {
  const { currentUser, clearUser } = useAuthStore()
  const navigate = useNavigate()
  const { data: overview } = useGetOverviewApiV1AdminOverviewGet({
    query: { staleTime: 60_000 },
  })
  const unassigned = overview?.unassigned_user_count ?? 0

  async function handleLogout() {
    await customInstance({ url: '/api/v1/auth/logout', method: 'POST' }).catch(() => null)
    clearUser()
    navigate('/login', { replace: true })
  }

  return (
    <nav
      style={{
        width: 220,
        minWidth: 220,
        height: '100%',
        background: A.sidebar,
        borderRight: `1px solid ${A.border}`,
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 12px',
        flexShrink: 0,
      }}
    >
      {/* Wordmark */}
      <div style={{ padding: '4px 8px 4px', marginBottom: 4 }}>
        <span
          style={{
            fontFamily: 'Geist Mono, monospace',
            fontSize: 13,
            fontWeight: 600,
            color: A.accent,
            letterSpacing: '0.04em',
          }}
        >
          WDIAG Admin
        </span>
      </div>

      {/* Back to app */}
      <Link
        to="/dashboard"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 8px 12px',
          fontSize: 12,
          color: A.fgMuted,
          textDecoration: 'none',
        }}
      >
        <ArrowLeftIcon />
        Back to app
      </Link>

      <div style={{ borderTop: `1px solid ${A.border}`, marginBottom: 8 }} />

      {/* Nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 6,
              background: isActive ? `rgba(59,130,246,0.15)` : 'transparent',
              color: isActive ? A.accent : A.fgMuted,
              textDecoration: 'none',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              position: 'relative',
            })}
          >
            <Icon />
            <span>{label}</span>
            {label === 'Users' && unassigned > 0 && (
              <span
                style={{
                  marginLeft: 'auto',
                  background: A.danger,
                  color: '#fff',
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 99,
                  minWidth: 18,
                  height: 18,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 5px',
                }}
              >
                {unassigned}
              </span>
            )}
          </NavLink>
        ))}
      </div>

      <div style={{ borderTop: `1px solid ${A.border}`, marginBottom: 8 }} />

      {/* Emergency */}
      <NavLink
        to="/admin/emergency"
        style={({ isActive }) => ({
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '8px 10px',
          borderRadius: 6,
          background: isActive ? `rgba(239,68,68,0.15)` : 'transparent',
          color: A.danger,
          textDecoration: 'none',
          fontSize: 13,
          fontWeight: 500,
        })}
      >
        <AlertTriangleIcon />
        Emergency
      </NavLink>

      <div style={{ borderTop: `1px solid ${A.border}`, marginTop: 8 }} />

      {/* Current admin + logout */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 8px 0',
        }}
      >
        <span
          style={{
            flex: 1,
            fontSize: 11,
            color: A.fgMuted,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={currentUser?.email}
        >
          {currentUser?.email}
        </span>
        <button
          onClick={handleLogout}
          title="Log out"
          style={{
            background: 'transparent',
            border: 'none',
            color: A.fgMuted,
            cursor: 'pointer',
            padding: 4,
            display: 'flex',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          <LogOutIcon />
        </button>
      </div>
    </nav>
  )
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return isMobile
}
