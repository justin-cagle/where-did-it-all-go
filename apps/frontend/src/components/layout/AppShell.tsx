import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { BottomNav } from './BottomNav'

const COMPACT_KEY = 'wdiag-sidebar-compact'

interface AppShellProps {
  children: ReactNode
  householdName?: string
}

export function AppShell({ children, householdName }: AppShellProps) {
  const [compact, setCompact] = useState(() => localStorage.getItem(COMPACT_KEY) === 'true')
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    setIsMobile(mq.matches)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const toggleCompact = () => {
    setCompact((prev) => {
      const next = !prev
      localStorage.setItem(COMPACT_KEY, String(next))
      return next
    })
  }

  return (
    <div
      style={{
        display: 'flex',
        height: '100dvh',
        background: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* Sidebar — desktop only */}
      {!isMobile && <Sidebar compact={compact} onToggleCompact={toggleCompact} />}

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar householdName={householdName} />

        <main
          style={{
            flex: 1,
            overflow: 'auto',
            padding: isMobile ? '16px 16px 80px' : '24px',
            background: 'var(--bg-primary)',
          }}
        >
          {children}
        </main>

        {/* Bottom nav — mobile only */}
        {isMobile && <BottomNav />}
      </div>
    </div>
  )
}
