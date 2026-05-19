import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, ExternalLink, ArrowLeft, CheckCircle2 } from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import { useCreateSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsPost } from '@/api/generated/ingest/ingest'

const ERR_INVALID = 'Invalid token. Check that you copied the full token from SimpleFIN Bridge.'
const ERR_CLAIMED =
  'This setup token has already been claimed. Request a new one from SimpleFIN Bridge.'
const ERR_NETWORK = 'Network error contacting SimpleFIN Bridge. Try again.'

function StepDone({
  label,
  created,
  mapped,
  onRestart,
}: {
  label: string
  created: number
  mapped: number
  onRestart: () => void
}) {
  const navigate = useNavigate()
  const total = created + mapped
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 14,
          padding: '36px 24px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          textAlign: 'center' as const,
        }}
      >
        <CheckCircle2 size={40} style={{ color: 'var(--success)' }} />
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)' }}>
            {label} connected
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-muted)', marginTop: 6 }}>
            {total} account{total !== 1 ? 's' : ''} configured ({created} created, {mapped} mapped)
          </div>
          <div
            style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 8, fontStyle: 'italic' }}
          >
            First sync starting now...
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10 }}>
        <button
          onClick={() => void navigate('/accounts')}
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: 600,
            padding: '9px 16px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Go to Accounts
        </button>
        <button
          onClick={onRestart}
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: 500,
            padding: '9px 16px',
            borderRadius: 8,
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
            border: '1px solid var(--border)',
            cursor: 'pointer',
          }}
        >
          Connect another account
        </button>
      </div>
    </div>
  )
}

export function ConnectPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { householdId } = useHousehold()

  const done = searchParams.get('done') === 'true'
  const doneLabel = searchParams.get('label') ?? 'SimpleFIN Connection'
  const doneCreated = parseInt(searchParams.get('created') ?? '0')
  const doneMapped = parseInt(searchParams.get('mapped') ?? '0')

  const [setupToken, setSetupToken] = useState('')
  const [label, setLabel] = useState('My accounts')
  const [showToken, setShowToken] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createMut = useCreateSyncConfigApiV1HouseholdsHouseholdIdIngestSyncConfigsPost()

  function handleConnect() {
    if (!householdId || !setupToken.trim()) return
    setError(null)
    createMut.mutate(
      {
        householdId,
        data: {
          provider: 'simplefin',
          setup_token: setupToken.trim(),
          label: label.trim() || null,
          sync_enabled: true,
        },
      },
      {
        onSuccess: (config) => {
          void navigate(`/settings/ingest/connect/${config.id}/map?wizard=true`)
        },
        onError: (err: unknown) => {
          const status = (err as { response?: { status?: number } })?.response?.status ?? 0
          const detail =
            (
              err as { response?: { data?: { detail?: string } } }
            )?.response?.data?.detail?.toLowerCase() ?? ''
          if (status === 409 || detail.includes('claimed')) {
            setError(ERR_CLAIMED)
          } else if (status === 400 || detail.includes('invalid') || detail.includes('token')) {
            setError(ERR_INVALID)
          } else {
            setError(ERR_NETWORK)
          }
        },
      }
    )
  }

  const content = done ? (
    <StepDone
      label={doneLabel}
      created={doneCreated}
      mapped={doneMapped}
      onRestart={() => void navigate('/settings/ingest/connect')}
    />
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0, lineHeight: 1.6 }}>
        SimpleFIN Bridge connects this app to your bank. You'll need a setup token from{' '}
        <a
          href="https://bridge.simplefin.org"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--accent)', textDecoration: 'none' }}
        >
          bridge.simplefin.org{' '}
          <ExternalLink size={11} style={{ display: 'inline', verticalAlign: 'middle' }} />
        </a>
        .
      </p>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
          Setup token
        </span>
        <div style={{ position: 'relative' as const }}>
          <input
            type={showToken ? 'text' : 'password'}
            value={setupToken}
            onChange={(e) => setSetupToken(e.target.value)}
            placeholder="Paste your setup token"
            autoComplete="off"
            style={{
              width: '100%',
              boxSizing: 'border-box' as const,
              fontSize: 13,
              padding: '9px 38px 9px 12px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              fontFamily: 'var(--font-mono)',
            }}
          />
          <button
            type="button"
            onClick={() => setShowToken((s) => !s)}
            style={{
              position: 'absolute' as const,
              right: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--fg-muted)',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {showToken ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
      </label>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>Label</span>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="My accounts"
          style={{
            fontSize: 13,
            padding: '9px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
          A friendly name for this connection
        </span>
      </label>

      {error && (
        <div
          style={{
            fontSize: 13,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
            color: 'var(--danger)',
            lineHeight: 1.5,
          }}
        >
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <a
          href="https://bridge.simplefin.org"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            fontWeight: 500,
            padding: '8px 16px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
            textDecoration: 'none',
            whiteSpace: 'nowrap' as const,
          }}
        >
          <ExternalLink size={13} /> Go to bridge.simplefin.org
        </a>
        <button
          onClick={handleConnect}
          disabled={!setupToken.trim() || createMut.isPending || !householdId}
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: 600,
            padding: '8px 16px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor: !setupToken.trim() || createMut.isPending ? 'not-allowed' : 'pointer',
            opacity: !setupToken.trim() || createMut.isPending ? 0.6 : 1,
          }}
        >
          {createMut.isPending ? 'Connecting...' : 'Connect'}
        </button>
      </div>
    </div>
  )

  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: '32px 24px' }}>
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
          margin: '0 0 20px',
          letterSpacing: '-0.01em',
        }}
      >
        {done ? 'Connection complete' : 'Connect a SimpleFIN account'}
      </h1>
      {content}
    </div>
  )
}
