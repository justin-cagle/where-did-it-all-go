import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PrivacyMode } from '@/lib/format'

interface User {
  id: string
  email: string
  display_name: string
  is_app_admin: boolean
}

interface AuthState {
  currentUser: User | null
  privacyMode: PrivacyMode
  isAuthenticated: boolean
  isLoading: boolean
  setUser: (user: User) => void
  clearUser: () => void
  setPrivacyMode: (mode: PrivacyMode) => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      currentUser: null,
      privacyMode: 'off',
      isAuthenticated: false,
      isLoading: true,
      setUser: (user) => set({ currentUser: user, isAuthenticated: true, isLoading: false }),
      clearUser: () => set({ currentUser: null, isAuthenticated: false, isLoading: false }),
      setPrivacyMode: (mode) => set({ privacyMode: mode }),
      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: 'wdiag-auth',
      partialize: (state) => ({ privacyMode: state.privacyMode }),
    }
  )
)
