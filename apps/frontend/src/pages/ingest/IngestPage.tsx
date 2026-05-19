import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw,
  Link2,
  MoreHorizontal,
  Upload,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import {
  useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet,
  useListImportJobsApiV1HouseholdsHouseholdIdIngestJobsGet,
  useTriggerSyncApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdTriggerPost,
  useDeleteSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdDelete,
  useUpdateSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdPatch,
} from '@/api/generated/ingest/ingest'
import type { SyncConfigOut } from '@/api/generated/model/syncConfigOut'
import type { ImportJobOut } from '@/api/generated/model/importJobOut'
import { useQueryClient } from '@tanstack/react-query'

const DATA_FRESHNESS_INFO =
  'SimpleFIN provides transactions posted as of yesterday. Banks share the previous day’s data overnight — this is how all third-party finance apps work, not a limitation of this app.\n\nFor today’s transactions, export a CSV or OFX from your bank’s website and import it below. There’s no limit on file imports.'

const FOOTER_MSG =
  'Need today’s transactions? SimpleFIN data reflects the previous business day. Export a CSV or OFX from your bank’s website and import it below for same-day transactions.'

const SYNC_INTERVALS = [1, 2, 4, 8, 24] as const

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return 'Never'
  const ms = Date.now() - new Date(iso).getTime()
  const mins = Math.round(ms / 60000)
  if (mins < 2) return 'Just now'
  if (mins < 60) return `${mins} minutes ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs !== 1 ? 's' : ''} ago`
  const days = Math.round(hrs / 24)
  return `${days} day${days !== 1 ? 's' : ''} ago`
}

function absoluteTime(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

const STATUS_CFG: Record<string, { color: string; label: string }> = {
  active: { color: 'var(--success)', label: 'Active' },
  warning: { color: 'var(--warning)', label: 'Warning' },
  rate_limited: { color: 'oklch(62% 0.18 42)', label: 'Rate limited' },
  error: { color: 'var(--danger)', label: 'Error' },
  disabled: { color: 'var(--fg-muted)', label: 'Disabled' },
}
const DEFAULT_STATUS = { color: 'var(--success)', label: 'Active' }

const JOB_STATUS_CFG: Record<string, { color: string; label: string; spinning?: boolean }> = {
  pending: { color: 'var(--fg-muted)', label: 'Pending', spinning: true },
  running: { color: 'var(--accent)', label: 'Running', spinning: true },
  completed: { color: 'var(--success)', label: 'Completed' },
  failed: { color: 'var(--danger)', label: 'Failed' },
}
const DEFAULT_JOB_STATUS = { color: 'var(--fg-muted)', label: 'Pending', spinning: true }

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_CFG[status] ?? DEFAULT_STATUS
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: `color-mix(in oklch, ${c.color} 14%, transparent)`,
        color: c.color,
        whiteSpace: 'nowrap' as const,
      }}
    >
      {c.label}
    </span>
  )
}

function JobStatusBadge({ status }: { status: string }) {
  const c = JOB_STATUS_CFG[status] ?? DEFAULT_JOB_STATUS
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
        background: `color-mix(in oklch, ${c.color} 14%, transparent)`,
        color: c.color,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        whiteSpace: 'nowrap' as const,
      }}
    >
      {c.spinning && <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />}
      {!c.spinning && status === 'completed' && <CheckCircle2 size={10} />}
      {!c.spinning && status === 'failed' && <XCircle size={10} />}
      {c.label}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  )
}

function SyncConfigRow({ config, householdId }: { config: SyncConfigOut; householdId: string }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const triggerMut = useTriggerSyncApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdTriggerPost()
  const deleteMut = useDeleteSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdDelete()
  const updateMut = useUpdateSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdPatch()

  const invalidate = () => {
    void qc.invalidateQueries({
      queryKey: [`/api/v1/households/${householdId}/ingest/sync-configs/`],
    })
  }

  function handleIntervalChange(e: React.ChangeEvent<HTMLSelectElement>) {
    updateMut.mutate(
      {
        householdId,
        configId: config.id,
        data: { sync_interval_hours: parseInt(e.target.value) },
      },
      { onSuccess: invalidate }
    )
  }

  function handleSync() {
    if (config.status === 'rate_limited') return
    triggerMut.mutate({ householdId, configId: config.id }, { onSuccess: invalidate })
  }

  function handleToggle() {
    updateMut.mutate(
      { householdId, configId: config.id, data: { sync_enabled: !config.sync_enabled } },
      { onSuccess: invalidate }
    )
    setMenuOpen(false)
  }

  function handleDelete() {
    deleteMut.mutate(
      { householdId, configId: config.id },
      {
        onSuccess: () => {
          setConfirmDelete(false)
          invalidate()
        },
      }
    )
  }

  const isRateLimited = config.status === 'rate_limited'
  const isWarning = config.requests_today >= 20

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {isWarning && !isRateLimited && (
        <div
          style={{
            fontSize: 12,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'color-mix(in oklch, var(--warning) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--warning) 30%, transparent)',
            color: 'var(--fg-primary)',
          }}
        >
          <strong>Approaching daily sync limit</strong>
          <br />
          You've used {config.requests_today} of 24 syncs today for{' '}
          {config.label ?? 'this connection'}. Your limit resets at approximately{' '}
          {config.requests_today_reset_at
            ? new Date(config.requests_today_reset_at + 'T00:00:00').toLocaleDateString()
            : 'midnight'}
          .
          <br />
          For today's transactions, export a CSV or OFX from your bank and import it below — file
          imports have no limit.{' '}
          <button
            onClick={() => {
              const el = document.getElementById('file-import-zone')
              el?.scrollIntoView({ behavior: 'smooth' })
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              padding: 0,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            Import a file →
          </button>
        </div>
      )}

      {isRateLimited && (
        <div
          style={{
            fontSize: 12,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'color-mix(in oklch, oklch(62% 0.18 42) 10%, transparent)',
            border: '1px solid color-mix(in oklch, oklch(62% 0.18 42) 30%, transparent)',
            color: 'var(--fg-primary)',
          }}
        >
          <strong>Sync paused for {config.label ?? 'this connection'}</strong>
          <br />
          SimpleFIN has paused syncing until{' '}
          {config.next_sync_at ? absoluteTime(config.next_sync_at) : 'tomorrow'} to prevent your
          account from being flagged for unusual activity. This is enforced by SimpleFIN, not by
          this app.
          <br />
          For today's transactions, export a CSV or OFX from your bank and import it below.{' '}
          <button
            onClick={() => {
              const el = document.getElementById('file-import-zone')
              el?.scrollIntoView({ behavior: 'smooth' })
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              padding: 0,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            Import a file →
          </button>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
              {config.label ?? 'SimpleFIN Connection'}
            </span>
            <StatusBadge status={config.status} />
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6, flexWrap: 'wrap' as const }}>
            {config.last_synced_at && (
              <span
                title={absoluteTime(config.last_synced_at)}
                style={{ fontSize: 12, color: 'var(--fg-muted)' }}
              >
                Synced {relativeTime(config.last_synced_at)}
              </span>
            )}
            {!isRateLimited && !config.last_error && config.next_sync_at && (
              <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                Next sync {absoluteTime(config.next_sync_at)}
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <select
            value={config.sync_interval_hours}
            onChange={handleIntervalChange}
            style={{
              fontSize: 12,
              padding: '4px 8px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              cursor: 'pointer',
            }}
          >
            {SYNC_INTERVALS.map((h) => (
              <option key={h} value={h}>
                Every {h}h
              </option>
            ))}
          </select>

          <button
            onClick={handleSync}
            disabled={isRateLimited || triggerMut.isPending}
            title={isRateLimited ? `Resumes at ${absoluteTime(config.next_sync_at)}` : 'Sync now'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              fontWeight: 500,
              padding: '5px 12px',
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: isRateLimited ? 'var(--fg-muted)' : 'var(--fg-primary)',
              cursor: isRateLimited ? 'not-allowed' : 'pointer',
            }}
          >
            <RefreshCw size={12} />
            Sync now
          </button>

          <div style={{ position: 'relative' as const }} ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '5px 8px',
                borderRadius: 7,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                cursor: 'pointer',
              }}
            >
              <MoreHorizontal size={14} />
            </button>
            {menuOpen && (
              <div
                style={{
                  position: 'absolute' as const,
                  right: 0,
                  top: '110%',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  boxShadow: 'var(--shadow)',
                  zIndex: 50,
                  minWidth: 160,
                  overflow: 'hidden',
                }}
              >
                {[
                  {
                    label: 'Edit mapping',
                    action: () => {
                      void navigate(`/settings/ingest/connect/${config.id}/map`)
                      setMenuOpen(false)
                    },
                  },
                  {
                    label: config.sync_enabled ? 'Disable' : 'Enable',
                    action: handleToggle,
                  },
                  {
                    label: 'Remove',
                    action: () => {
                      setConfirmDelete(true)
                      setMenuOpen(false)
                    },
                    danger: true,
                  },
                ].map(({ label, action, danger }) => (
                  <button
                    key={label}
                    onClick={action}
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left' as const,
                      padding: '9px 14px',
                      fontSize: 13,
                      background: 'none',
                      border: 'none',
                      color: danger ? 'var(--danger)' : 'var(--fg-primary)',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.background =
                        'var(--bg-secondary)'
                    }}
                    onMouseLeave={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.background = 'none'
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {confirmDelete && (
        <div
          style={{
            padding: '12px 14px',
            background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          <div style={{ marginBottom: 10, color: 'var(--fg-primary)' }}>
            This will stop syncing. Existing transactions are not affected.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleDelete}
              disabled={deleteMut.isPending}
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: '5px 14px',
                borderRadius: 6,
                background: 'var(--danger)',
                color: '#fff',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Remove
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              style={{
                fontSize: 12,
                padding: '5px 14px',
                borderRadius: 6,
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ImportJobRow({ job }: { job: ImportJobOut }) {
  const navigate = useNavigate()
  const isActive = job.status === 'pending' || job.status === 'running'
  const filename = job.filename
    ? job.filename.length > 40
      ? job.filename.slice(0, 38) + '…'
      : job.filename
    : ''

  const sourceBadgeColor =
    job.source === 'csv_upload'
      ? 'var(--accent)'
      : job.source === 'simplefin'
        ? 'var(--success)'
        : 'var(--info)'

  return (
    <div
      onClick={() => void navigate(`/settings/ingest/upload/${job.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') void navigate(`/settings/ingest/upload/${job.id}`)
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        borderRadius: 8,
        cursor: 'pointer',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          padding: '2px 7px',
          borderRadius: 99,
          background: `color-mix(in oklch, ${sourceBadgeColor} 14%, transparent)`,
          color: sourceBadgeColor,
          flexShrink: 0,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.04em',
        }}
      >
        {job.source.replace('_', ' ')}
      </span>
      <span
        style={{
          fontSize: 13,
          color: 'var(--fg-primary)',
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap' as const,
          flex: 1,
        }}
      >
        {filename || '—'}
      </span>
      <JobStatusBadge status={job.status} />
      <span style={{ fontSize: 12, color: 'var(--fg-muted)', whiteSpace: 'nowrap' as const }}>
        {job.imported_count} imported{' '}
        {job.duplicate_count > 0 ? `· ${job.duplicate_count} dup` : ''}
      </span>
      <span style={{ fontSize: 12, color: 'var(--fg-muted)', whiteSpace: 'nowrap' as const }}>
        {new Date(job.created_at).toLocaleDateString()}
      </span>
      {isActive && <Clock size={13} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />}
    </div>
  )
}

export function IngestPage() {
  const navigate = useNavigate()
  const { householdId } = useHousehold()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const { data: syncConfigs, isLoading: syncLoading } =
    useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet(householdId ?? '', {
      query: { enabled: !!householdId, staleTime: 30_000 },
    })

  const { data: jobs, isLoading: jobsLoading } =
    useListImportJobsApiV1HouseholdsHouseholdIdIngestJobsGet(householdId ?? '', undefined, {
      query: { enabled: !!householdId, staleTime: 10_000 },
    })

  function handleFile(file: File) {
    void navigate('/settings/ingest/upload', { state: { file } })
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  if (!householdId) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32, maxWidth: 760 }}>
      <div>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: 0,
            letterSpacing: '-0.01em',
          }}
        >
          Connected Accounts
        </h1>
        <div
          style={{
            marginTop: 8,
            padding: '10px 14px',
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--fg-muted)',
            lineHeight: 1.6,
          }}
        >
          {DATA_FRESHNESS_INFO.split('\n\n').map((para, i) => (
            <p key={i} style={{ margin: i > 0 ? '8px 0 0' : 0 }}>
              {para}
            </p>
          ))}
        </div>
      </div>

      {/* Connected accounts */}
      <section>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <h2
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: 0,
            }}
          >
            SimpleFIN connections
          </h2>
          <button
            onClick={() => void navigate('/settings/ingest/connect')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
              fontWeight: 500,
              padding: '7px 14px',
              borderRadius: 8,
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            <Link2 size={13} />
            Connect a SimpleFIN account
          </button>
        </div>

        {syncLoading ? (
          <div
            style={{
              height: 80,
              background: 'var(--bg-elevated)',
              borderRadius: 12,
              border: '1px solid var(--border)',
              opacity: 0.6,
            }}
          />
        ) : !syncConfigs || syncConfigs.length === 0 ? (
          <div
            style={{
              padding: '40px 24px',
              textAlign: 'center' as const,
              color: 'var(--fg-muted)',
              background: 'var(--bg-elevated)',
              borderRadius: 12,
              border: '1px dashed var(--border)',
              fontSize: 14,
            }}
          >
            No connected accounts yet — connect a SimpleFIN account to start syncing
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {syncConfigs.map((c) => (
              <SyncConfigRow key={c.id} config={c} householdId={householdId} />
            ))}
          </div>
        )}
      </section>

      {/* Data freshness footer */}
      <div
        style={{
          padding: '10px 14px',
          background: 'color-mix(in oklch, var(--info) 8%, transparent)',
          border: '1px solid color-mix(in oklch, var(--info) 20%, transparent)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--fg-muted)',
        }}
      >
        {FOOTER_MSG}
      </div>

      {/* File import */}
      <section id="file-import-zone">
        <h2
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: '0 0 12px',
          }}
        >
          File import
        </h2>

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragOver(true)
          }}
          onDragLeave={() => setIsDragOver(false)}
          style={{
            border: `2px dashed ${isDragOver ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 12,
            padding: '32px 24px',
            textAlign: 'center' as const,
            background: isDragOver
              ? 'color-mix(in oklch, var(--accent) 5%, transparent)'
              : 'var(--bg-elevated)',
            transition: 'all 0.15s',
            cursor: 'default',
            marginBottom: 16,
          }}
        >
          <Upload size={28} style={{ color: 'var(--fg-muted)', marginBottom: 10 }} />
          <div style={{ fontSize: 14, color: 'var(--fg-primary)', fontWeight: 500 }}>
            Drop your bank file here
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 4 }}>
            or{' '}
            <button
              onClick={() => fileInputRef.current?.click()}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent)',
                cursor: 'pointer',
                padding: 0,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Browse files
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 8 }}>
            Accepted: OFX, QFX, CSV
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".ofx,.qfx,.csv"
            style={{ display: 'none' }}
            onChange={handleFileInput}
          />
        </div>

        {/* Recent imports */}
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: 'var(--fg-muted)',
              marginBottom: 8,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.05em',
            }}
          >
            Recent imports
          </div>

          {jobsLoading ? (
            <div
              style={{
                height: 60,
                background: 'var(--bg-elevated)',
                borderRadius: 8,
                opacity: 0.6,
              }}
            />
          ) : !jobs || jobs.length === 0 ? (
            <div
              style={{
                padding: '20px',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
                background: 'var(--bg-elevated)',
                borderRadius: 8,
                border: '1px solid var(--border)',
              }}
            >
              <FileText
                size={18}
                style={{ marginBottom: 6, display: 'block', margin: '0 auto 6px' }}
              />
              No file imports yet
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {jobs.map((j) => (
                <ImportJobRow key={j.id} job={j} />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
