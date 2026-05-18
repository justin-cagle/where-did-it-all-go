import { useState, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetSystemApiV1AdminSystemGet,
  getGetSystemApiV1AdminSystemGetQueryKey,
  useForceLogoutAllApiV1AdminForceLogoutAllPost,
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
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    return `${Math.floor(diffHr / 24)}d ago`
  } catch {
    return iso
  }
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
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

export function AdminSystemPage() {
  const qc = useQueryClient()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [stepUpLogoutAll, setStepUpLogoutAll] = useState(false)
  const [logoutConfirmInput, setLogoutConfirmInput] = useState('')
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set())

  const { data: system, isLoading } = useGetSystemApiV1AdminSystemGet({
    query: { staleTime: 30_000 },
  })
  const forceLogoutAll = useForceLogoutAllApiV1AdminForceLogoutAllPost()

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      void qc.invalidateQueries({ queryKey: getGetSystemApiV1AdminSystemGetQueryKey() })
    }, 30_000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [qc])

  const tableRowCounts = system?.table_row_counts as Record<string, number> | undefined

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {stepUpLogoutAll && (
        <StepUpModal
          onSuccess={() => {
            setStepUpLogoutAll(false)
            setShowLogoutConfirm(true)
          }}
          onCancel={() => setStepUpLogoutAll(false)}
        />
      )}

      {showLogoutConfirm && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: 24,
              width: 400,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.danger }}>
              Force logout all users
            </div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              This will log out all users immediately. Type{' '}
              <strong style={{ color: A.fg }}>LOGOUT_ALL</strong> to confirm.
            </div>
            <input
              value={logoutConfirmInput}
              onChange={(e) => setLogoutConfirmInput(e.target.value)}
              style={{
                padding: '7px 10px',
                borderRadius: 6,
                fontSize: 13,
                background: A.bg,
                border: `1px solid ${A.border}`,
                color: A.fg,
                outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setShowLogoutConfirm(false)
                  setLogoutConfirmInput('')
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: 'transparent',
                  border: `1px solid ${A.border}`,
                  color: A.fgMuted,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                disabled={logoutConfirmInput !== 'LOGOUT_ALL'}
                onClick={async () => {
                  await forceLogoutAll.mutateAsync({ data: { confirm: 'LOGOUT_ALL' } })
                  setShowLogoutConfirm(false)
                  setLogoutConfirmInput('')
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: logoutConfirmInput === 'LOGOUT_ALL' ? A.danger : A.border,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: logoutConfirmInput === 'LOGOUT_ALL' ? 'pointer' : 'not-allowed',
                }}
              >
                Log out all
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>System</h1>
          <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
            Infrastructure health and diagnostics
          </p>
        </div>
        <button
          onClick={() =>
            void qc.invalidateQueries({ queryKey: getGetSystemApiV1AdminSystemGetQueryKey() })
          }
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

      {isLoading ? (
        <div style={{ color: A.fgMuted, fontSize: 13 }}>Loading...</div>
      ) : (
        system && (
          <>
            {/* Workers */}
            <Section title="Worker Pools">
              <Row
                label="Fast pool"
                value={
                  <StatusBadge
                    ok={system.worker_fast_healthy}
                    labelTrue="Running"
                    labelFalse="Stopped"
                  />
                }
              />
              <Row
                label="Slow pool"
                value={
                  <StatusBadge
                    ok={system.worker_slow_healthy}
                    labelTrue="Running"
                    labelFalse="Stopped"
                  />
                }
              />
              <Row label="Pending jobs" value={system.pending_job_count} />
            </Section>

            {/* Failed jobs */}
            <Section title="Failed Jobs (last 50)">
              {system.failed_jobs.length === 0 ? (
                <div style={{ fontSize: 13, color: A.success }}>No failed jobs — all clear</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {system.failed_jobs.map((job) => {
                    const expanded = expandedJobs.has(job.job_id)
                    return (
                      <div
                        key={job.job_id}
                        style={{
                          background: A.bg,
                          borderRadius: 6,
                          border: `1px solid ${A.border}`,
                        }}
                      >
                        <button
                          onClick={() => {
                            const next = new Set(expandedJobs)
                            if (expanded) next.delete(job.job_id)
                            else next.add(job.job_id)
                            setExpandedJobs(next)
                          }}
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            textAlign: 'left',
                            cursor: 'pointer',
                            background: 'transparent',
                            border: 'none',
                            display: 'flex',
                            gap: 12,
                            alignItems: 'center',
                          }}
                        >
                          <span style={{ fontSize: 13, fontWeight: 500, color: A.fg, flex: 1 }}>
                            {job.function}
                          </span>
                          <span style={{ fontSize: 12, color: A.fgMuted }}>
                            {relativeTime(new Date(job.score * 1000).toISOString())}
                          </span>
                          <span style={{ fontSize: 12, color: A.fgMuted }}>
                            {expanded ? '▲' : '▼'}
                          </span>
                        </button>
                        {expanded && (
                          <div
                            style={{
                              padding: '0 12px 10px',
                              fontSize: 12,
                              color: A.fgMuted,
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {job.job_id}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </Section>

            {/* Database */}
            <Section title="Database">
              <Row label="Total size" value={formatBytes(system.db_size_bytes)} />
              {tableRowCounts &&
                Object.entries(tableRowCounts).map(([table, count]) => (
                  <Row key={table} label={table} value={count.toLocaleString()} />
                ))}
              <div
                style={{
                  borderTop: `1px solid ${A.border}`,
                  paddingTop: 10,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <Row
                  label="Current revision"
                  value={
                    <code
                      style={{
                        fontSize: 11,
                        fontFamily: 'monospace',
                        background: 'rgba(255,255,255,0.05)',
                        padding: '1px 5px',
                        borderRadius: 3,
                      }}
                    >
                      {system.alembic_current}
                    </code>
                  }
                />
                <Row
                  label="Head revision"
                  value={
                    <code
                      style={{
                        fontSize: 11,
                        fontFamily: 'monospace',
                        background: 'rgba(255,255,255,0.05)',
                        padding: '1px 5px',
                        borderRadius: 3,
                      }}
                    >
                      {system.alembic_head}
                    </code>
                  }
                />
                <Row
                  label="Status"
                  value={
                    system.alembic_up_to_date ? (
                      <span style={{ fontSize: 12, color: A.success }}>Up to date</span>
                    ) : (
                      <span style={{ fontSize: 12, color: A.warning }}>Migrations pending</span>
                    )
                  }
                />
              </div>
            </Section>

            {/* Redis */}
            <Section title="Redis">
              <Row label="Memory used" value={formatBytes(system.redis_memory_bytes)} />
              <Row label="Connected clients" value={system.redis_connected_clients} />
              <Row label="DB keys" value={system.redis_db_keys.toLocaleString()} />
            </Section>

            {/* Sessions */}
            <Section title="Sessions">
              <Row label="Active sessions" value={system.active_session_count} />
              <button
                onClick={() => setStepUpLogoutAll(true)}
                style={{
                  alignSelf: 'flex-start',
                  padding: '7px 14px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: 'transparent',
                  border: `1px solid ${A.danger}`,
                  color: A.danger,
                  fontSize: 13,
                }}
              >
                Force logout all users
              </button>
            </Section>

            {/* Uptime */}
            <Section title="Uptime">
              <Row label="Started at" value={new Date(system.app_started_at).toLocaleString()} />
              <Row
                label="Running for"
                value={relativeTime(system.app_started_at).replace(' ago', '')}
              />
            </Section>
          </>
        )
      )}
    </div>
  )
}
