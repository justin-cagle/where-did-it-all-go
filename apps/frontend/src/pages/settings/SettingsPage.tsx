import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useMeApiV1AuthMeGet } from '@/api/generated/households/households'
import { User, Home, Tag, Sparkles, Shield, AlertTriangle } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/settings/profile', label: 'Profile', icon: User, description: 'Display name and TOTP' },
  {
    to: '/settings/household',
    label: 'Household',
    icon: Home,
    description: 'Name, visibility, members',
  },
  {
    to: '/settings/classification',
    label: 'Classification',
    icon: Tag,
    description: 'Categories, tags, rules',
  },
  {
    to: '/settings/insights',
    label: 'Insights',
    icon: Sparkles,
    description: 'AI providers and budget',
  },
  {
    to: '/settings/security',
    label: 'Security',
    icon: Shield,
    description: 'Password and sessions',
  },
]

export function SettingsLayout() {
  const location = useLocation()
  const { data: me } = useMeApiV1AuthMeGet()

  const isRoot = location.pathname === '/settings'
  const isAdminOnly = me?.is_app_admin === true
  const allItems = isAdminOnly
    ? [
        ...NAV_ITEMS,
        {
          to: '/settings/danger',
          label: 'Danger zone',
          icon: AlertTriangle,
          description: 'Irreversible household actions',
        },
      ]
    : NAV_ITEMS

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Sidebar */}
      <nav
        style={{
          width: 220,
          minWidth: 220,
          borderRight: '1px solid var(--border)',
          padding: '20px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          flexShrink: 0,
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '4px 10px 8px',
          }}
        >
          Settings
        </div>
        {allItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 6,
              background: isActive
                ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--fg-secondary)',
              textDecoration: 'none',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              transition: 'background 0.1s, color 0.1s',
            })}
          >
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px', minWidth: 0 }}>
        {isRoot ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <h1
              style={{
                fontSize: 22,
                fontWeight: 600,
                color: 'var(--fg-primary)',
                margin: 0,
                letterSpacing: '-0.01em',
              }}
            >
              Settings
            </h1>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 10,
                marginTop: 8,
              }}
            >
              {allItems.map(({ to, label, icon: Icon, description }) => (
                <NavLink
                  key={to}
                  to={to}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 12,
                    padding: '14px 16px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    textDecoration: 'none',
                    transition: 'border-color 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    ;(e.currentTarget as HTMLAnchorElement).style.borderColor =
                      'var(--border-strong)'
                  }}
                  onMouseLeave={(e) => {
                    ;(e.currentTarget as HTMLAnchorElement).style.borderColor = 'var(--border)'
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={15} style={{ color: 'var(--accent)' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
                      {label}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                      {description}
                    </div>
                  </div>
                </NavLink>
              ))}
            </div>
          </div>
        ) : (
          <Outlet />
        )}
      </div>
    </div>
  )
}
