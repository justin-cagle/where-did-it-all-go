import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetOverviewApiV1AdminOverviewGet,
  getGetOverviewApiV1AdminOverviewGetQueryKey,
  useListNotificationsApiV1AdminNotificationsGet,
  getListNotificationsApiV1AdminNotificationsGetQueryKey,
  useMarkReadApiV1AdminNotificationsNotificationIdReadPost,
  useMarkAllReadApiV1AdminNotificationsReadAllPost,
  useGetRegistrationApiV1AdminRegistrationGet,
  getGetRegistrationApiV1AdminRegistrationGetQueryKey,
  useUpdateRegistrationApiV1AdminRegistrationPost,
} from '@/api/generated/admin/admin'
import { formatBytes } from '@/lib/format'
import { StepUpModal } from '@/components/admin/StepUpModal'

const A = {
  bg: '#0a0f1a',
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
  danger: '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
}

function relativeTime(iso: string): string {
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const diffSec = Math.floor(diffMs / 1000)
    if (diffSec < 60) return 'just now'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    return `${diffDay}d ago`
  } catch {
    return iso
  }
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: A.bgRaised,
        border: `1px solid ${A.border}`,
        borderRadius: 10,
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: A.fgMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  )
}

function Row({
  label,
  value,
  valueColor,
}: {
  label: string
  value: React.ReactNode
  valueColor?: string
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 13, color: A.fgMuted }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 500, color: valueColor ?? A.fg }}>{value}</span>
    </div>
  )
}

function StatusBadge({
  ok,
  labelTrue,
  labelFalse,
}: {
  ok: boolean
  labelTrue: string
  labelFalse: string
}) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: ok ? `rgba(16,185,129,0.15)` : `rgba(239,68,68,0.15)`,
        color: ok ? A.success : A.danger,
      }}
    >
      {ok ? labelTrue : labelFalse}
    </span>
  )
}

function RefreshIcon() {
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
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  )
}

export function AdminOverviewPage() {
  const qc = useQueryClient()
  const [stepUpFor, setStepUpFor] = useState<'toggle' | null>(null)
  const [pendingToggle, setPendingToggle] = useState<boolean | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: overview, isLoading } = useGetOverviewApiV1AdminOverviewGet({
    query: { staleTime: 30_000 },
  })
  const { data: notifications } = useListNotificationsApiV1AdminNotificationsGet({ read: false })
  const { data: regSettings } = useGetRegistrationApiV1AdminRegistrationGet()

  const markRead = useMarkReadApiV1AdminNotificationsNotificationIdReadPost()
  const markAllRead = useMarkAllReadApiV1AdminNotificationsReadAllPost()
  const updateReg = useUpdateRegistrationApiV1AdminRegistrationPost()

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      void qc.invalidateQueries({ queryKey: getGetOverviewApiV1AdminOverviewGetQueryKey() })
    }, 30_000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [qc])

  function handleRefresh() {
    void qc.invalidateQueries({ queryKey: getGetOverviewApiV1AdminOverviewGetQueryKey() })
  }

  async function doUpdateReg(allow: boolean, limit?: number | null, ttl?: number) {
    await updateReg.mutateAsync({
      data: {
        allow_registration: allow,
        registration_limit: limit ?? undefined,
        unassigned_account_ttl_days: ttl,
      },
    })
    await qc.invalidateQueries({ queryKey: getGetRegistrationApiV1AdminRegistrationGetQueryKey() })
    await qc.invalidateQueries({ queryKey: getGetOverviewApiV1AdminOverviewGetQueryKey() })
  }

  const lastBackupRaw = overview?.last_backup
  const backupOk =
    lastBackupRaw != null &&
    typeof lastBackupRaw === 'string' &&
    (() => {
      try {
        const diffH = (Date.now() - new Date(lastBackupRaw).getTime()) / 3600_000
        return diffH < 24
      } catch {
        return false
      }
    })()

  const unreadNotifs = notifications?.items ?? []

  if (isLoading) {
    return <div style={{ padding: 32, color: A.fgMuted }}>Loading...</div>
  }

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24 }}>
      {stepUpFor === 'toggle' && (
        <StepUpModal
          onSuccess={async () => {
            setStepUpFor(null)
            if (pendingToggle !== null && regSettings) {
              await doUpdateReg(
                pendingToggle,
                regSettings.registration_limit,
                regSettings.unassigned_account_ttl_days
              )
              setPendingToggle(null)
            }
          }}
          onCancel={() => {
            setStepUpFor(null)
            setPendingToggle(null)
          }}
        />
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>Overview</h1>
          <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
            Instance health and quick stats
          </p>
        </div>
        <button
          onClick={handleRefresh}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 12px',
            borderRadius: 6,
            background: 'transparent',
            border: `1px solid ${A.border}`,
            color: A.fgMuted,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          <RefreshIcon />
          Refresh
        </button>
      </div>

      {/* 2x2 cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card title="Users">
          <Row label="Active users" value={overview?.active_user_count ?? '-'} />
          <Row
            label="Unassigned"
            value={
              overview && overview.unassigned_user_count > 0 ? (
                <Link
                  to="/admin/users?unassigned=true"
                  style={{
                    color: A.warning,
                    fontWeight: 500,
                    fontSize: 13,
                    textDecoration: 'none',
                  }}
                >
                  {overview.unassigned_user_count}
                </Link>
              ) : (
                (overview?.unassigned_user_count ?? '-')
              )
            }
            valueColor={overview && overview.unassigned_user_count > 0 ? A.warning : undefined}
          />
          <Row
            label="Registration"
            value={
              overview?.allow_registration ? `Open (${overview.active_count_vs_limit})` : 'Closed'
            }
          />
        </Card>

        <Card title="Households">
          <Row label="Total" value={overview?.household_count ?? '-'} />
        </Card>

        <Card title="System">
          <Row
            label="Worker (fast)"
            value={
              <StatusBadge
                ok={overview?.worker_fast_healthy ?? false}
                labelTrue="Running"
                labelFalse="Stopped"
              />
            }
          />
          <Row
            label="Worker (slow)"
            value={
              <StatusBadge
                ok={overview?.worker_slow_healthy ?? false}
                labelTrue="Running"
                labelFalse="Stopped"
              />
            }
          />
          <Row label="Pending jobs" value={overview?.pending_job_count ?? '-'} />
          <Row
            label="Failed jobs (24h)"
            value={overview?.failed_job_count_24h ?? '-'}
            valueColor={overview && overview.failed_job_count_24h > 0 ? A.danger : undefined}
          />
          <Row label="DB size" value={overview ? formatBytes(overview.db_size_bytes) : '-'} />
          <Row
            label="Last backup"
            value={
              lastBackupRaw && typeof lastBackupRaw === 'string'
                ? relativeTime(lastBackupRaw)
                : 'Never'
            }
            valueColor={!backupOk ? A.danger : undefined}
          />
        </Card>

        <Card title="Registration Settings">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: A.fgMuted }}>Allow registration</span>
            <button
              onClick={() => {
                const next = !(regSettings?.allow_registration ?? false)
                setPendingToggle(next)
                setStepUpFor('toggle')
              }}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                border: 'none',
                background: regSettings?.allow_registration
                  ? `rgba(16,185,129,0.15)`
                  : `rgba(239,68,68,0.15)`,
                color: regSettings?.allow_registration ? A.success : A.danger,
              }}
            >
              {regSettings?.allow_registration ? 'Enabled' : 'Disabled'}
            </button>
          </div>
          {regSettings?.allow_registration && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span style={{ fontSize: 13, color: A.fgMuted }}>Registration limit</span>
              <input
                type="number"
                min="1"
                defaultValue={regSettings.registration_limit ?? ''}
                placeholder="unlimited"
                onBlur={async (e) => {
                  const v = e.target.value
                  const limit = v ? parseInt(v) : undefined
                  await doUpdateReg(true, limit, regSettings.unassigned_account_ttl_days)
                }}
                style={{
                  width: 96,
                  padding: '4px 8px',
                  borderRadius: 6,
                  fontSize: 13,
                  background: A.bg,
                  border: `1px solid ${A.border}`,
                  color: A.fg,
                  textAlign: 'right',
                }}
              />
            </div>
          )}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span style={{ fontSize: 13, color: A.fgMuted }}>Unassigned TTL (days)</span>
            <input
              type="number"
              defaultValue={regSettings?.unassigned_account_ttl_days ?? 7}
              onBlur={async (e) => {
                const v = parseInt(e.target.value)
                if (!isNaN(v) && regSettings) {
                  await doUpdateReg(
                    regSettings.allow_registration,
                    regSettings.registration_limit,
                    v
                  )
                }
              }}
              style={{
                width: 60,
                padding: '4px 8px',
                borderRadius: 6,
                fontSize: 13,
                background: A.bg,
                border: `1px solid ${A.border}`,
                color: A.fg,
                textAlign: 'right',
              }}
            />
          </div>
        </Card>
      </div>

      {/* Notifications */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: A.fgMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Notifications
          </div>
          {unreadNotifs.length > 0 && (
            <button
              onClick={async () => {
                await markAllRead.mutateAsync()
                await qc.invalidateQueries({
                  queryKey: getListNotificationsApiV1AdminNotificationsGetQueryKey(),
                })
              }}
              style={{
                fontSize: 12,
                color: A.accent,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              Mark all read
            </button>
          )}
        </div>

        {unreadNotifs.length === 0 ? (
          <div style={{ fontSize: 13, color: A.fgMuted }}>No notifications</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {unreadNotifs.map((n) => (
              <div
                key={n.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 12,
                  padding: '10px 12px',
                  background: A.bg,
                  borderRadius: 6,
                  border: `1px solid ${A.border}`,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: A.fg }}>{n.title}</div>
                  <div style={{ fontSize: 12, color: A.fgMuted, marginTop: 2 }}>{n.body}</div>
                  <div style={{ fontSize: 11, color: A.fgMuted, marginTop: 4 }}>
                    {relativeTime(n.created_at)}
                  </div>
                </div>
                <button
                  onClick={async () => {
                    await markRead.mutateAsync({ notificationId: n.id })
                    await qc.invalidateQueries({
                      queryKey: getListNotificationsApiV1AdminNotificationsGetQueryKey(),
                    })
                  }}
                  style={{
                    fontSize: 11,
                    color: A.fgMuted,
                    background: 'transparent',
                    border: `1px solid ${A.border}`,
                    borderRadius: 4,
                    padding: '3px 8px',
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  Mark read
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
