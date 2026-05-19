import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import { useGetImportJobApiV1HouseholdsHouseholdIdIngestJobsImportJobIdGet } from '@/api/generated/ingest/ingest'
import type { ImportJobOut } from '@/api/generated/model/importJobOut'

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle2 size={20} style={{ color: 'var(--success)' }} />
  if (status === 'failed') return <XCircle size={20} style={{ color: 'var(--danger)' }} />
  return (
    <Loader2 size={20} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
  )
}

function ProgressBar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0
  return (
    <div
      style={{
        height: 6,
        background: 'var(--bg-secondary)',
        borderRadius: 99,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${pct}%`,
          background: 'var(--accent)',
          borderRadius: 99,
          transition: 'width 0.3s ease',
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div
      style={{
        flex: 1,
        padding: '14px 16px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        textAlign: 'center' as const,
        minWidth: 80,
      }}
    >
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          color: color ?? 'var(--fg-primary)',
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function ErrorTable({ errors }: { errors: unknown }) {
  if (!errors || !Array.isArray(errors) || errors.length === 0) return null
  const rows = errors.slice(0, 50) as Array<{ row?: number; message?: string }>
  return (
    <div style={{ marginTop: 4 }}>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--fg-muted)',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.05em',
          marginBottom: 8,
        }}
      >
        Errors ({rows.length}
        {errors.length > 50 ? '+' : ''})
      </div>
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          overflow: 'hidden',
        }}
      >
        {rows.map((e, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: 12,
              padding: '8px 12px',
              fontSize: 12,
              borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none',
            }}
          >
            {e.row != null && (
              <span
                style={{ color: 'var(--fg-muted)', flexShrink: 0, fontFamily: 'var(--font-mono)' }}
              >
                row {e.row}
              </span>
            )}
            <span style={{ color: 'var(--danger)' }}>{e.message ?? String(e)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function JobDetail({ job }: { job: ImportJobOut }) {
  const isActive = job.status === 'pending' || job.status === 'running'
  const filename = job.filename ? job.filename : job.source

  const statusColor =
    job.status === 'completed'
      ? 'var(--success)'
      : job.status === 'failed'
        ? 'var(--danger)'
        : 'var(--accent)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '16px 20px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
        }}
      >
        <StatusIcon status={job.status} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap' as const,
            }}
          >
            {filename}
          </div>
          <div style={{ fontSize: 12, color: statusColor, marginTop: 2, fontWeight: 500 }}>
            {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
            {isActive && '...'}
          </div>
        </div>
        {job.completed_at && (
          <span style={{ fontSize: 12, color: 'var(--fg-muted)', flexShrink: 0 }}>
            {new Date(job.completed_at).toLocaleString()}
          </span>
        )}
      </div>

      {isActive && job.row_count > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              color: 'var(--fg-muted)',
            }}
          >
            <span>Processing rows</span>
            <span>
              {job.imported_count + job.duplicate_count + job.error_count} / {job.row_count}
            </span>
          </div>
          <ProgressBar
            value={job.imported_count + job.duplicate_count + job.error_count}
            total={job.row_count}
          />
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const }}>
        <StatBox label="Total rows" value={job.row_count} />
        <StatBox label="Imported" value={job.imported_count} color="var(--success)" />
        <StatBox label="Duplicates" value={job.duplicate_count} color="var(--fg-muted)" />
        <StatBox
          label="Errors"
          value={job.error_count}
          color={job.error_count > 0 ? 'var(--danger)' : undefined}
        />
      </div>

      {job.status === 'completed' && job.imported_count > 0 && (
        <Link
          to={`/transactions?import_job_id=${job.id}`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--accent)',
            textDecoration: 'none',
          }}
        >
          <ExternalLink size={13} />
          View {job.imported_count} imported transaction{job.imported_count !== 1 ? 's' : ''}
        </Link>
      )}

      {job.error_count > 0 && job.error_detail && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--danger)',
              marginBottom: 10,
            }}
          >
            <AlertTriangle size={14} />
            {job.error_count} row{job.error_count !== 1 ? 's' : ''} could not be imported
          </div>
          <ErrorTable
            errors={
              typeof job.error_detail === 'string'
                ? (() => {
                    try {
                      return JSON.parse(job.error_detail) as unknown
                    } catch {
                      return [{ message: job.error_detail }]
                    }
                  })()
                : job.error_detail
            }
          />
        </div>
      )}

      {job.status === 'failed' && job.error_detail && job.error_count === 0 && (
        <div
          style={{
            padding: '12px 14px',
            background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 25%, transparent)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--danger)',
          }}
        >
          {typeof job.error_detail === 'string'
            ? job.error_detail
            : JSON.stringify(job.error_detail)}
        </div>
      )}
    </div>
  )
}

export function ImportJobDetailPage() {
  const { importJobId } = useParams<{ importJobId: string }>()
  const navigate = useNavigate()
  const { householdId } = useHousehold()

  const { data: job, isLoading } =
    useGetImportJobApiV1HouseholdsHouseholdIdIngestJobsImportJobIdGet(
      householdId ?? '',
      importJobId ?? '',
      {
        query: {
          enabled: !!householdId && !!importJobId,
          refetchInterval: (query) => {
            const status = query.state.data?.status
            return status === 'pending' || status === 'running' ? 3000 : false
          },
        },
      }
    )

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '32px 24px' }}>
      <button
        onClick={() => void navigate('/settings/ingest')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          color: 'var(--fg-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '0 0 20px',
          marginBottom: 4,
        }}
      >
        <ArrowLeft size={14} /> Connected Accounts
      </button>

      <h1
        style={{
          fontSize: 20,
          fontWeight: 600,
          color: 'var(--fg-primary)',
          margin: '0 0 24px',
          letterSpacing: '-0.01em',
        }}
      >
        Import details
      </h1>

      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[80, 40, 60].map((h, i) => (
            <div
              key={i}
              style={{
                height: h,
                background: 'var(--bg-elevated)',
                borderRadius: 10,
                opacity: 0.6,
              }}
            />
          ))}
        </div>
      )}

      {!isLoading && job && <JobDetail job={job} />}

      {!isLoading && !job && (
        <div
          style={{
            fontSize: 14,
            color: 'var(--fg-muted)',
            textAlign: 'center' as const,
            padding: '40px 0',
          }}
        >
          Import job not found.
        </div>
      )}
    </div>
  )
}
