import { useState, useRef, useEffect, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { useTheme } from '@/providers/ThemeProvider'
import { customInstance } from '@/api/client'
import type { PrivacyMode } from '@/lib/format'

interface TopBarProps {
  householdName?: string
}

export function TopBar({ householdName }: TopBarProps) {
  const { currentUser, privacyMode, setPrivacyMode, clearUser } = useAuthStore()
  const { theme, setTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [themeMenuOpen, setThemeMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const themeMenuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const cyclePrivacy = () => {
    const order: PrivacyMode[] = ['off', 'partial_blur', 'full_blur']
    const next = order[(order.indexOf(privacyMode) + 1) % order.length] ?? 'off'
    setPrivacyMode(next)
  }

  const handleLogout = async () => {
    try {
      await customInstance({ url: '/api/v1/auth/logout', method: 'POST' })
    } catch {
      // ignore — clear local state regardless
    }
    clearUser()
    navigate('/login', { replace: true })
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target as Node)) {
        setThemeMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <header
      style={{
        height: 52,
        background: 'var(--bg-elevated)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 12,
        flexShrink: 0,
      }}
    >
      {/* Household name */}
      <span
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--fg-secondary)',
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {householdName ?? ''}
      </span>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {/* Privacy toggle */}
        <IconButton
          onClick={cyclePrivacy}
          aria-label={`Privacy: ${privacyMode}`}
          title={`Privacy mode: ${privacyMode}`}
        >
          {privacyMode === 'off' ? (
            <EyeIcon />
          ) : privacyMode === 'partial_blur' ? (
            <EyePartialIcon />
          ) : (
            <EyeOffIcon />
          )}
        </IconButton>

        {/* Separator */}
        <div
          style={{
            width: 1,
            height: 18,
            background: 'var(--border)',
            margin: '0 2px',
            flexShrink: 0,
          }}
        />

        {/* Theme dropdown */}
        <div ref={themeMenuRef} style={{ position: 'relative' }}>
          <IconButton
            onClick={() => setThemeMenuOpen((v) => !v)}
            aria-label={`Theme: ${theme}`}
            title={`Theme: ${theme}`}
          >
            {theme === 'dark' ? <MoonIcon /> : theme === 'light' ? <SunIcon /> : <MonitorIcon />}
          </IconButton>
          {themeMenuOpen && (
            <div
              role="menu"
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                minWidth: 130,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                boxShadow: 'var(--shadow)',
                padding: '4px',
                zIndex: 50,
              }}
            >
              {(
                [
                  { value: 'system', label: 'System', icon: <MonitorIcon /> },
                  { value: 'light', label: 'Light', icon: <SunIcon /> },
                  { value: 'dark', label: 'Dark', icon: <MoonIcon /> },
                ] as const
              ).map(({ value, label, icon }) => (
                <ThemeMenuItem
                  key={value}
                  label={label}
                  icon={icon}
                  active={theme === value}
                  onClick={() => {
                    setTheme(value)
                    setThemeMenuOpen(false)
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* User menu */}
        <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '4px 8px 4px 4px',
              borderRadius: 8,
              border: '1px solid transparent',
              background: 'transparent',
              cursor: 'pointer',
              color: 'var(--fg-primary)',
              fontFamily: 'var(--font-sans)',
              fontSize: 13,
              fontWeight: 500,
              transition: 'background 0.1s',
            }}
            aria-expanded={userMenuOpen}
            aria-haspopup="menu"
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-fg)',
                fontSize: 11,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {initials(currentUser?.display_name ?? '')}
            </div>
            <span
              style={{
                maxWidth: 120,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {currentUser?.display_name ?? ''}
            </span>
          </button>

          {userMenuOpen && (
            <div
              role="menu"
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                minWidth: 160,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                boxShadow: 'var(--shadow)',
                padding: '4px',
                zIndex: 50,
              }}
            >
              <MenuItem onClick={handleLogout} danger>
                Log out
              </MenuItem>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function IconButton({
  children,
  onClick,
  'aria-label': ariaLabel,
  title,
}: {
  children: React.ReactNode
  onClick: () => void
  'aria-label': string
  title?: string
}) {
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel}
      title={title}
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        border: 'none',
        background: 'transparent',
        color: 'var(--fg-secondary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 0.1s, color 0.1s',
      }}
    >
      {children}
    </button>
  )
}

function MenuItem({
  children,
  onClick,
  danger,
}: {
  children: React.ReactNode
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        padding: '8px 12px',
        textAlign: 'left',
        background: 'transparent',
        border: 'none',
        borderRadius: 6,
        fontSize: 13,
        color: danger ? 'var(--danger)' : 'var(--fg-primary)',
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {children}
    </button>
  )
}

function ThemeMenuItem({
  label,
  icon,
  active,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  active: boolean
  onClick: () => void
}) {
  const style: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    width: '100%',
    padding: '7px 10px',
    background: active ? 'color-mix(in oklch, var(--accent) 10%, transparent)' : 'transparent',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    color: active ? 'var(--accent)' : 'var(--fg-primary)',
    cursor: 'pointer',
    fontFamily: 'var(--font-sans)',
    textAlign: 'left',
  }
  return (
    <button role="menuitem" onClick={onClick} style={style}>
      <span style={{ color: active ? 'var(--accent)' : 'var(--fg-muted)' }}>{icon}</span>
      {label}
      {active && (
        <span style={{ marginLeft: 'auto', color: 'var(--accent)', fontSize: 11 }}>&#10003;</span>
      )}
    </button>
  )
}

function initials(name: string): string {
  return name
    .split(' ')
    .map((p) => p[0] ?? '')
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function EyeIcon() {
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
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyePartialIcon() {
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
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <path d="M9 12a3 3 0 0 1 6 0" />
    </svg>
  )
}

function EyeOffIcon() {
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
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

function MonitorIcon() {
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
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  )
}

function SunIcon() {
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
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon() {
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
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}
