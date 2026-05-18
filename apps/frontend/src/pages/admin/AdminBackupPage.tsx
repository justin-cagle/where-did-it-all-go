import { useState, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  useListBackupRunsApiV1AdminBackupRunsGet,
  getListBackupRunsApiV1AdminBackupRunsGetQueryKey,
  useTriggerBackupApiV1AdminBackupTriggerPost,
  useGetBackupConfigApiV1AdminBackupConfigGet,
  getGetBackupConfigApiV1AdminBackupConfigGetQueryKey,
  useUpsertBackupConfigApiV1AdminBackupConfigPost,
  useDeleteS3ApiV1AdminBackupConfigS3Delete,
  useTestS3ApiV1AdminBackupConfigTestS3Post,
} from '@/api/generated/admin/admin'
import { formatBytes } from '@/lib/format'
import { StepUpModal } from '@/components/admin/StepUpModal'
import type { BackupStatus } from '@/api/generated/model'

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

function StatusBadge({ status }: { status: BackupStatus }) {
  const color = status === 'success' ? A.success : status === 'failed' ? A.danger : A.warning
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: `${color}22`,
        color,
      }}
    >
      {status}
    </span>
  )
}

const s3Schema = z.object({
  s3_endpoint: z.string().url('Must be a URL').optional().or(z.literal('')),
  s3_bucket: z.string().min(1, 'Required'),
  s3_access_key: z.string().min(1, 'Required'),
  s3_secret_key: z.string().min(1, 'Required'),
  s3_path_prefix: z.string().default('wdiag-backups'),
  s3_enabled: z.boolean().default(false),
  local_retention_days: z.coerce.number().min(1).default(30),
})
type S3FormData = z.infer<typeof s3Schema>

const inputStyle = {
  padding: '7px 10px',
  borderRadius: 6,
  fontSize: 13,
  background: A.bg,
  border: `1px solid ${A.border}`,
  color: A.fg,
  outline: 'none',
  width: '100%',
}

export function AdminBackupPage() {
  const qc = useQueryClient()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [stepUpFor, setStepUpFor] = useState<'trigger' | 'saveS3' | 'deleteS3' | null>(null)
  const [pendingS3, setPendingS3] = useState<S3FormData | null>(null)
  const [s3TestResult, setS3TestResult] = useState<{
    success: boolean
    detail: string | null
  } | null>(null)
  const [showS3, setShowS3] = useState(false)
  const [s3DeleteConfirm, setS3DeleteConfirm] = useState(false)
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set())

  const { data: runs } = useListBackupRunsApiV1AdminBackupRunsGet(
    {},
    { query: { staleTime: 30_000 } }
  )
  const { data: config } = useGetBackupConfigApiV1AdminBackupConfigGet()
  const trigger = useTriggerBackupApiV1AdminBackupTriggerPost()
  const upsertConfig = useUpsertBackupConfigApiV1AdminBackupConfigPost()
  const deleteS3 = useDeleteS3ApiV1AdminBackupConfigS3Delete()
  const testS3 = useTestS3ApiV1AdminBackupConfigTestS3Post()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<S3FormData>({
    resolver: zodResolver(s3Schema),
    defaultValues: {
      s3_endpoint: config?.s3_endpoint ?? '',
      s3_bucket: config?.s3_bucket ?? '',
      s3_access_key: config?.s3_access_key ?? '',
      s3_secret_key: '',
      s3_path_prefix: config?.s3_path_prefix ?? 'wdiag-backups',
      s3_enabled: config?.s3_enabled ?? false,
      local_retention_days: config?.local_retention_days ?? 30,
    },
  })

  const runList = runs?.items ?? []
  const latestRun = runList[0]
  const hasRunning = runList.some((r) => r.status === 'running')

  const latestOk =
    latestRun &&
    latestRun.status === 'success' &&
    latestRun.started_at &&
    Date.now() - new Date(latestRun.started_at).getTime() < 86_400_000

  useEffect(() => {
    if (!hasRunning) return
    intervalRef.current = setInterval(() => {
      void qc.invalidateQueries({ queryKey: getListBackupRunsApiV1AdminBackupRunsGetQueryKey() })
    }, 5_000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [qc, hasRunning])

  async function doTrigger() {
    await trigger.mutateAsync()
    await qc.invalidateQueries({ queryKey: getListBackupRunsApiV1AdminBackupRunsGetQueryKey() })
  }

  async function doSaveS3(data: S3FormData) {
    await upsertConfig.mutateAsync({
      data: {
        s3_endpoint: data.s3_endpoint || null,
        s3_bucket: data.s3_bucket || null,
        s3_access_key: data.s3_access_key || null,
        s3_secret_key: data.s3_secret_key || null,
        s3_path_prefix: data.s3_path_prefix,
        s3_enabled: data.s3_enabled,
        local_retention_days: data.local_retention_days,
      },
    })
    await qc.invalidateQueries({ queryKey: getGetBackupConfigApiV1AdminBackupConfigGetQueryKey() })
  }

  async function doTestS3() {
    setS3TestResult(null)
    try {
      const result = await testS3.mutateAsync()
      setS3TestResult({ success: result.success, detail: result.error_detail ?? null })
    } catch {
      setS3TestResult({ success: false, detail: 'Request failed' })
    }
  }

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24 }}>
      {stepUpFor === 'trigger' && (
        <StepUpModal
          onSuccess={async () => {
            setStepUpFor(null)
            await doTrigger()
          }}
          onCancel={() => setStepUpFor(null)}
        />
      )}
      {stepUpFor === 'saveS3' && pendingS3 && (
        <StepUpModal
          onSuccess={async () => {
            const d = pendingS3
            setStepUpFor(null)
            setPendingS3(null)
            await doSaveS3(d)
          }}
          onCancel={() => {
            setStepUpFor(null)
            setPendingS3(null)
          }}
        />
      )}
      {stepUpFor === 'deleteS3' && (
        <StepUpModal
          onSuccess={async () => {
            setStepUpFor(null)
            await deleteS3.mutateAsync()
            await qc.invalidateQueries({
              queryKey: getGetBackupConfigApiV1AdminBackupConfigGetQueryKey(),
            })
          }}
          onCancel={() => setStepUpFor(null)}
        />
      )}
      {s3DeleteConfirm && (
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
              width: 380,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Remove S3 config</div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              This will disable cloud backup. Local backups will continue.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setS3DeleteConfirm(false)}
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
                onClick={() => {
                  setS3DeleteConfirm(false)
                  setStepUpFor('deleteS3')
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: A.danger,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>Backup</h1>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
          Database backup management
        </p>
      </div>

      {/* Last backup */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${latestOk ? A.border : A.warning}`,
          borderRadius: 10,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
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
          Last Backup
        </div>
        {latestRun ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Status</span>
              <StatusBadge status={latestRun.status} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Started</span>
              <span style={{ fontSize: 13, color: A.fg }}>
                {relativeTime(latestRun.started_at)}
              </span>
            </div>
            {latestRun.size_bytes != null && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: A.fgMuted }}>Size</span>
                <span style={{ fontSize: 13, color: A.fg }}>
                  {formatBytes(latestRun.size_bytes)}
                </span>
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: 13, color: A.fgMuted }}>No backups yet</div>
        )}
        <button
          onClick={() => setStepUpFor('trigger')}
          style={{
            alignSelf: 'flex-start',
            padding: '7px 14px',
            borderRadius: 6,
            background: A.accent,
            border: 'none',
            color: '#fff',
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
            marginTop: 4,
          }}
        >
          Back up now
        </button>
      </div>

      {/* Backup runs table */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: A.fgMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '14px 16px',
            borderBottom: `1px solid ${A.border}`,
          }}
        >
          Recent Runs
        </div>
        {runList.length === 0 ? (
          <div style={{ padding: '16px', fontSize: 13, color: A.fgMuted }}>No backup runs</div>
        ) : (
          runList.map((run, i) => {
            const expanded = expandedErrors.has(run.id)
            return (
              <div key={run.id} style={{ borderTop: i === 0 ? 'none' : `1px solid ${A.border}` }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '100px 120px 1fr 80px',
                    gap: 0,
                    padding: '10px 16px',
                    alignItems: 'center',
                  }}
                >
                  <StatusBadge status={run.status} />
                  <span style={{ fontSize: 12, color: A.fgMuted }}>{run.triggered_by}</span>
                  <span style={{ fontSize: 12, color: A.fgMuted }}>
                    {relativeTime(run.started_at)}
                  </span>
                  {run.error_detail && (
                    <button
                      onClick={() => {
                        const next = new Set(expandedErrors)
                        if (expanded) next.delete(run.id)
                        else next.add(run.id)
                        setExpandedErrors(next)
                      }}
                      style={{
                        fontSize: 11,
                        color: A.fgMuted,
                        background: 'transparent',
                        border: `1px solid ${A.border}`,
                        borderRadius: 4,
                        padding: '2px 6px',
                        cursor: 'pointer',
                      }}
                    >
                      {expanded ? 'Hide' : 'Error'}
                    </button>
                  )}
                </div>
                {expanded && run.error_detail && (
                  <div
                    style={{
                      padding: '0 16px 10px',
                      fontSize: 12,
                      color: A.danger,
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {run.error_detail}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* BYOB note */}
      <div
        style={{
          background: `rgba(59,130,246,0.08)`,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: '14px 16px',
          fontSize: 13,
          color: A.fgMuted,
        }}
      >
        You can use your own backup solution instead of or in addition to the built-in options. The
        nightly dump is a standard Postgres logical backup (.sql.gz). Mount the backup volume in
        your Docker configuration to access it from the host.
      </div>

      {/* S3 config */}
      <div>
        <button
          onClick={() => setShowS3((p) => !p)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 0',
            background: 'transparent',
            border: 'none',
            color: A.fg,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <span>{showS3 ? '▲' : '▼'}</span> Cloud backup (S3, optional)
        </button>
        {showS3 && (
          <form
            onSubmit={handleSubmit((data) => {
              setPendingS3(data)
              setStepUpFor('saveS3')
            })}
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: '18px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
              marginTop: 8,
            }}
          >
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              S3 backup is optional. Local backups run nightly regardless. Configure S3 to store an
              offsite copy automatically. Supports AWS S3, Backblaze B2, Wasabi, MinIO, and any
              S3-compatible endpoint.
            </div>
            {[
              {
                name: 's3_endpoint' as const,
                label: 'S3 Endpoint URL',
                placeholder: 'https://s3.amazonaws.com or your S3-compatible endpoint',
              },
              { name: 's3_bucket' as const, label: 'Bucket name' },
              { name: 's3_path_prefix' as const, label: 'Path prefix' },
              { name: 's3_access_key' as const, label: 'Access key' },
              { name: 's3_secret_key' as const, label: 'Secret key' },
            ].map(({ name, label, placeholder }) => (
              <div key={name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: A.fgMuted }}>{label}</label>
                <input
                  {...register(name)}
                  type={name === 's3_secret_key' ? 'password' : 'text'}
                  placeholder={placeholder}
                  style={inputStyle}
                />
                {errors[name] && (
                  <span style={{ fontSize: 12, color: A.danger }}>{errors[name]?.message}</span>
                )}
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                {...register('s3_enabled')}
                type="checkbox"
                id="s3_enabled"
                style={{ width: 14, height: 14, accentColor: A.accent }}
              />
              <label htmlFor="s3_enabled" style={{ fontSize: 13, color: A.fg, cursor: 'pointer' }}>
                Enable S3 backup
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="submit"
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: A.accent,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Save
              </button>
              <button
                type="button"
                onClick={doTestS3}
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
                Test connection
              </button>
              {config?.s3_enabled && (
                <button
                  type="button"
                  onClick={() => setS3DeleteConfirm(true)}
                  style={{
                    padding: '7px 14px',
                    borderRadius: 6,
                    background: 'transparent',
                    border: `1px solid ${A.danger}`,
                    color: A.danger,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Remove S3 config
                </button>
              )}
            </div>
            {s3TestResult && (
              <div style={{ fontSize: 13, color: s3TestResult.success ? A.success : A.danger }}>
                {s3TestResult.success
                  ? 'Connection successful'
                  : `Failed: ${s3TestResult.detail ?? 'Unknown error'}`}
              </div>
            )}

            <div
              style={{
                borderTop: `1px solid ${A.border}`,
                paddingTop: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: A.fgMuted }}>Local retention</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: 13, color: A.fgMuted }}>Keep local backups for</label>
                <input
                  {...register('local_retention_days')}
                  type="number"
                  style={{ ...inputStyle, width: 70 }}
                />
                <span style={{ fontSize: 13, color: A.fgMuted }}>days</span>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
