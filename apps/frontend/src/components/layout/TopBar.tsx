import { useState, useRef, useEffect } from 'react'
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
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const cyclePrivacy = () => {
    const order: PrivacyMode[] = ['off', 'partial_blur', 'full_blur']
    const next = order[(order.indexOf(privacyMode) + 1) % order.length] ?? 'off'
    setPrivacyMode(next)
  }

  const toggleTheme = () => {
    if (theme === 'system') {
      setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
    } else {
      setTheme(theme === 'dark' ? 'light' : 'dark')
    }
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
          {privacyMode === 'off' ? <EyeIcon /> : <EyeOffIcon />}
        </IconButton>

        {/* Theme toggle */}
        <IconButton onClick={toggleTheme} aria-label="Toggle theme">
          {resolvedTheme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </IconButton>

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
