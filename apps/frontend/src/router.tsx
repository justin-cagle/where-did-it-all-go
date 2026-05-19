import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { AuthGuard } from '@/components/AuthGuard'
import { AppShell } from '@/components/layout/AppShell'
import { AdminGuard } from '@/components/admin/AdminGuard'
import { AdminShell } from '@/components/admin/AdminShell'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { TotpSetupPage } from '@/pages/auth/TotpSetupPage'
import { OnboardingPage } from '@/pages/onboarding/OnboardingPage'
import { WaitingPage } from '@/pages/WaitingPage'
import {
  DashboardPage,
  AccountsPage,
  TransactionsPage,
  BudgetPage,
  GoalsPage,
  DebtsPage,
  CalendarPage,
} from '@/pages/DashboardPage'
import { AccountDetailPage } from '@/pages/accounts/AccountDetailPage'
import { BudgetDetailPage } from '@/pages/budgets/BudgetDetailPage'
import { DebtPlanPage } from '@/pages/debts/DebtPlanPage'
import { GoalDetailPage } from '@/pages/goals/GoalDetailPage'
import { ClassificationPage } from '@/pages/classification/ClassificationPage'
import { SettingsLayout } from '@/pages/settings/SettingsPage'
import { ProfilePage } from '@/pages/settings/ProfilePage'
import { HouseholdPage } from '@/pages/settings/HouseholdPage'
import { InsightsSettingsPage } from '@/pages/settings/InsightsSettingsPage'
import { SecurityPage } from '@/pages/settings/SecurityPage'
import { IngestPage } from '@/pages/ingest/IngestPage'
import { ConnectPage } from '@/pages/ingest/ConnectPage'
import { AccountMappingPage } from '@/pages/ingest/AccountMappingPage'
import { FileUploadPage } from '@/pages/ingest/FileUploadPage'
import { ImportJobDetailPage } from '@/pages/ingest/ImportJobDetailPage'
import { AdminOverviewPage } from '@/pages/admin/AdminOverviewPage'
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage'
import { AdminUserDetailPage } from '@/pages/admin/AdminUserDetailPage'
import { AdminHouseholdsPage } from '@/pages/admin/AdminHouseholdsPage'
import { AdminHouseholdDetailPage } from '@/pages/admin/AdminHouseholdDetailPage'
import { AdminSystemPage } from '@/pages/admin/AdminSystemPage'
import { AdminSMTPPage } from '@/pages/admin/AdminSMTPPage'
import { AdminBackupPage } from '@/pages/admin/AdminBackupPage'
import { AdminEmergencyPage } from '@/pages/admin/AdminEmergencyPage'

const ProjectionsPage = lazy(() =>
  import('@/pages/projections/ProjectionsPage').then((m) => ({ default: m.ProjectionsPage }))
)
const InsightsPage = lazy(() =>
  import('@/pages/insights/InsightsPage').then((m) => ({ default: m.InsightsPage }))
)

function PageSkeleton() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: 200,
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          border: '3px solid var(--border)',
          borderTopColor: 'var(--accent)',
          animation: 'spin 0.7s linear infinite',
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

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

  /* Authed — no AppShell, no household required */
  {
    path: '/onboarding',
    element: (
      <AuthGuard requireHousehold={false}>
        <OnboardingPage />
      </AuthGuard>
    ),
  },
  {
    path: '/waiting',
    element: (
      <AuthGuard requireHousehold={false}>
        <WaitingPage />
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
    path: '/budget/:budgetId',
    element: (
      <AuthedShell>
        <BudgetDetailPage />
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
    path: '/goals/:goalId',
    element: (
      <AuthedShell>
        <GoalDetailPage />
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
    path: '/debts/plan/:planId',
    element: (
      <AuthedShell>
        <DebtPlanPage />
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
    path: '/projections',
    element: (
      <AuthedShell>
        <Suspense fallback={<PageSkeleton />}>
          <ProjectionsPage />
        </Suspense>
      </AuthedShell>
    ),
  },
  {
    path: '/insights',
    element: (
      <AuthedShell>
        <Suspense fallback={<PageSkeleton />}>
          <InsightsPage />
        </Suspense>
      </AuthedShell>
    ),
  },
  {
    path: '/settings',
    element: (
      <AuthedShell>
        <SettingsLayout />
      </AuthedShell>
    ),
    children: [
      { path: 'profile', element: <ProfilePage /> },
      { path: 'household', element: <HouseholdPage /> },
      { path: 'ingest', element: <IngestPage /> },
      { path: 'classification', element: <ClassificationPage /> },
      { path: 'insights', element: <InsightsSettingsPage /> },
      { path: 'security', element: <SecurityPage /> },
    ],
  },

  /* Ingest wizard pages — standalone (no settings sidebar) */
  {
    path: '/settings/ingest/connect',
    element: (
      <AuthedShell>
        <ConnectPage />
      </AuthedShell>
    ),
  },
  {
    path: '/settings/ingest/connect/:syncConfigId/map',
    element: (
      <AuthedShell>
        <AccountMappingPage />
      </AuthedShell>
    ),
  },
  {
    path: '/settings/ingest/upload',
    element: (
      <AuthedShell>
        <FileUploadPage />
      </AuthedShell>
    ),
  },
  {
    path: '/settings/ingest/upload/:importJobId',
    element: (
      <AuthedShell>
        <ImportJobDetailPage />
      </AuthedShell>
    ),
  },

  /* Admin — wrapped in AdminGuard + AdminShell */
  {
    path: '/admin',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminOverviewPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/users',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminUsersPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/users/:id',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminUserDetailPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/households',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminHouseholdsPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/households/:id',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminHouseholdDetailPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/system',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminSystemPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/smtp',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminSMTPPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/backup',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminBackupPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
  {
    path: '/admin/emergency',
    element: (
      <AuthGuard>
        <AdminGuard>
          <AdminShell>
            <AdminEmergencyPage />
          </AdminShell>
        </AdminGuard>
      </AuthGuard>
    ),
  },
])
