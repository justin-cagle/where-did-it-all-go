import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AuthGuard } from '@/components/AuthGuard'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { TotpSetupPage } from '@/pages/auth/TotpSetupPage'
import { OnboardingPage } from '@/pages/onboarding/OnboardingPage'
import {
  DashboardPage,
  AccountsPage,
  TransactionsPage,
  BudgetPage,
  GoalsPage,
  DebtsPage,
  CalendarPage,
  SettingsPage,
} from '@/pages/DashboardPage'
import { AccountDetailPage } from '@/pages/accounts/AccountDetailPage'

function AuthedShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  )
}

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/dashboard" replace /> },

  /* Public */
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/register/totp-setup', element: <TotpSetupPage /> },

  /* Authed — no AppShell */
  {
    path: '/onboarding',
    element: (
      <AuthGuard>
        <OnboardingPage />
      </AuthGuard>
    ),
  },

  /* Authed — with AppShell */
  {
    path: '/dashboard',
    element: (
      <AuthedShell>
        <DashboardPage />
      </AuthedShell>
    ),
  },
  {
    path: '/accounts',
    element: (
      <AuthedShell>
        <AccountsPage />
      </AuthedShell>
    ),
  },
  {
    path: '/accounts/:accountId',
    element: (
      <AuthedShell>
        <AccountDetailPage />
      </AuthedShell>
    ),
  },
  {
    path: '/transactions',
    element: (
      <AuthedShell>
        <TransactionsPage />
      </AuthedShell>
    ),
  },
  {
    path: '/budget',
    element: (
      <AuthedShell>
        <BudgetPage />
      </AuthedShell>
    ),
  },
  {
    path: '/goals',
    element: (
      <AuthedShell>
        <GoalsPage />
      </AuthedShell>
    ),
  },
  {
    path: '/debts',
    element: (
      <AuthedShell>
        <DebtsPage />
      </AuthedShell>
    ),
  },
  {
    path: '/calendar',
    element: (
      <AuthedShell>
        <CalendarPage />
      </AuthedShell>
    ),
  },
  {
    path: '/settings',
    element: (
      <AuthedShell>
        <SettingsPage />
      </AuthedShell>
    ),
  },
])
