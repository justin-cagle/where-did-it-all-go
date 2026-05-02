import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PrivacyMode } from '@/lib/format-amount'

/**
 * UI store — cross-cutting client state (Zustand).
 *
 * Privacy mode and theme are persisted per device/session,
 * not per household (per DECISIONS.md R4E / R10 D11).
 */
interface UIState {
  privacyMode: PrivacyMode
  setPrivacyMode: (mode: PrivacyMode) => void

  theme: 'light' | 'dark' | 'system'
  setTheme: (theme: 'light' | 'dark' | 'system') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      privacyMode: 'off',
      setPrivacyMode: (mode) => set({ privacyMode: mode }),

      theme: 'system',
      setTheme: (theme) => set({ theme }),
    }),
    { name: 'wdiag-ui' }
  )
)
