import { useParams, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import {
  useGetInvitationMetadataApiV1InvitationsTokenGet,
  useAcceptInvitationApiV1InvitationsTokenAcceptPost,
  useDeclineInvitationApiV1InvitationsTokenDeclinePost,
} from '@/api/generated/households/households'
import { customInstance, ApiError } from '@/api/client'
import { useState } from 'react'

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'var(--bg-primary)',
      }}
    >
      <div
        style={{ width: '100%', maxWidth: 440, display: 'flex', flexDirection: 'column', gap: 24 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              style={{
                color: 'var(--accent-fg)',
                fontFamily: 'var(--font-mono)',
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              $
            </span>
          </div>
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--fg-primary)',
            }}
          >
            wdiag
          </span>
        </div>
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 16,
            padding: '28px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            boxShadow: 'var(--shadow)',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

function RoleBadge({ role }: { role: string }) {
  const label = role === 'owner' ? 'Owner' : role === 'member' ? 'Member' : role
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 99,
        fontSize: 12,
        fontWeight: 500,
        background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
        color: 'var(--accent)',
        border: '1px solid color-mix(in oklch, var(--accent) 30%, transparent)',
      }}
    >
      {label}
    </span>
  )
}

function ExpiryLine({ expiresAt }: { expiresAt: string }) {
  const dt = new Date(expiresAt)
  const now = new Date()
  const diffHours = Math.round((dt.getTime() - now.getTime()) / 3_600_000)
  let label: string
  if (diffHours < 0) {
    label = 'Expired'
  } else if (diffHours < 1) {
    label = 'Expires in less than 1 hour'
  } else if (diffHours < 24) {
    label = `Expires in ${diffHours} hour${diffHours === 1 ? '' : 's'}`
  } else {
    const days = Math.ceil(diffHours / 24)
    label = `Expires in ${days} day${days === 1 ? '' : 's'}`
  }
  return <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{label}</span>
}

export function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { isAuthenticated, currentUser } = useAuthStore()
  const [declined, setDeclined] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const {
    data: meta,
    isLoading,
    error,
  } = useGetInvitationMetadataApiV1InvitationsTokenGet(token ?? '', { query: { enabled: !!token } })

  const acceptMutation = useAcceptInvitationApiV1InvitationsTokenAcceptPost()
  const declineMutation = useDeclineInvitationApiV1InvitationsTokenDeclinePost()

  if (!token) {
    return (
      <PageShell>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Invalid link
        </h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.6 }}>
          This invitation link is not valid.
        </p>
      </PageShell>
    )
  }

  if (isLoading) {
    return (
      <PageShell>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            color: 'var(--fg-muted)',
            fontSize: 14,
          }}
        >
          <div
            style={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              border: '2px solid var(--border)',
              borderTopColor: 'var(--accent)',
              animation: 'spin 0.7s linear infinite',
              flexShrink: 0,
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          Loading invitation...
        </div>
      </PageShell>
    )
  }

  if (error || !meta) {
    const apiErr = error as ApiError | null
    const status = apiErr?.status

    let title = 'Invitation not found'
    let body = 'This invitation link is invalid or has been removed.'

    if (status === 410 || meta?.status === 'expired') {
      title = 'Invitation expired'
      body = 'This invitation link has expired. Ask the household owner to send a new one.'
    } else if (status === 409 || meta?.status === 'accepted') {
      title = 'Already accepted'
      body = 'This invitation has already been accepted.'
    } else if (meta?.status === 'revoked') {
      title = 'Invitation revoked'
      body = 'This invitation has been revoked by the household owner.'
    } else if (meta?.status === 'declined') {
      title = 'Invitation declined'
      body = 'This invitation was previously declined.'
    }

    return (
      <PageShell>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          {title}
        </h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.6 }}>
          {body}
        </p>
        <a href="/login" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'none' }}>
          Back to login
        </a>
      </PageShell>
    )
  }

  if (meta.status !== 'pending') {
    const titles: Record<string, string> = {
      accepted: 'Already accepted',
      expired: 'Invitation expired',
      revoked: 'Invitation revoked',
      declined: 'Invitation declined',
    }
    const bodies: Record<string, string> = {
      accepted: 'This invitation has already been accepted.',
      expired: 'This invitation link has expired. Ask the household owner to send a new one.',
      revoked: 'This invitation has been revoked by the household owner.',
      declined: 'This invitation was previously declined.',
    }
    return (
      <PageShell>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          {titles[meta.status] ?? 'Invitation unavailable'}
        </h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.6 }}>
          {bodies[meta.status] ?? 'This invitation is no longer valid.'}
        </p>
        <a href="/login" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'none' }}>
          Back to login
        </a>
      </PageShell>
    )
  }

  if (declined) {
    return (
      <PageShell>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Invitation declined
        </h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.6 }}>
          You have declined the invitation to join <strong>{meta.household_name}</strong>.
        </p>
        <a href="/login" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'none' }}>
          Back to login
        </a>
      </PageShell>
    )
  }

  if (accepted) {
    return (
      <PageShell>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Welcome!
        </h1>
        <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.6 }}>
          You have joined <strong>{meta.household_name}</strong>. Redirecting...
        </p>
      </PageShell>
    )
  }

  const redirectParam = encodeURIComponent(`/invite/${token}`)

  const handleAccept = async () => {
    setActionError(null)
    try {
      await acceptMutation.mutateAsync({ token })
      setAccepted(true)
      setTimeout(() => navigate('/dashboard', { replace: true }), 1500)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setActionError('Email mismatch: this invite was sent to a different address.')
        } else if (err.status === 410) {
          setActionError('This invitation has expired.')
        } else {
          setActionError('Failed to accept. Try again.')
        }
      } else {
        setActionError('Failed to accept. Try again.')
      }
    }
  }

  const handleDecline = async () => {
    setActionError(null)
    try {
      await declineMutation.mutateAsync({ token })
      setDeclined(true)
    } catch {
      setActionError('Failed to decline. Try again.')
    }
  }

  const emailMismatch =
    isAuthenticated &&
    currentUser &&
    currentUser.email.toLowerCase() !== meta.invited_email.toLowerCase()

  return (
    <PageShell>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          You have been invited
        </h1>
        <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
          {meta.invited_by_name} invited you to join a household
        </p>
      </div>

      {/* Household card */}
      <div
        style={{
          padding: '14px 16px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
          {meta.household_name}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RoleBadge role={meta.invited_email ? 'member' : 'member'} />
          <ExpiryLine expiresAt={meta.expires_at} />
        </div>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Sent to {meta.invited_email}</div>
      </div>

      {/* Not authenticated — show login / register options */}
      {!isAuthenticated && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: 0 }}>
            Sign in or create an account to accept this invitation.
          </p>
          <a
            href={`/login?redirect=${redirectParam}`}
            style={{
              display: 'block',
              padding: '10px 16px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              textDecoration: 'none',
              textAlign: 'center',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Sign in
          </a>
          <a
            href={`/register?email=${encodeURIComponent(meta.invited_email)}&redirect=${redirectParam}`}
            style={{
              display: 'block',
              padding: '10px 16px',
              background: 'none',
              border: '1px solid var(--border)',
              color: 'var(--fg-primary)',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
              textDecoration: 'none',
              textAlign: 'center',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Create account
          </a>
        </div>
      )}

      {/* Authenticated + email mismatch */}
      {isAuthenticated && emailMismatch && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div
            style={{
              padding: '12px 14px',
              background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
              border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
              borderRadius: 8,
              fontSize: 13,
              color: 'var(--danger)',
              lineHeight: 1.5,
            }}
          >
            This invite was sent to <strong>{meta.invited_email}</strong>, but you are signed in as{' '}
            <strong>{currentUser?.email}</strong>. Sign out and sign in with the correct account.
          </div>
          <button
            type="button"
            onClick={async () => {
              try {
                await customInstance({ url: '/api/v1/auth/logout', method: 'POST' })
              } finally {
                useAuthStore.getState().clearUser()
                navigate(`/login?redirect=${redirectParam}`, { replace: true })
              }
            }}
            style={{
              padding: '10px 16px',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 14,
              color: 'var(--fg-primary)',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Sign out
          </button>
        </div>
      )}

      {/* Authenticated + email match — accept / decline */}
      {isAuthenticated && !emailMismatch && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {actionError && (
            <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{actionError}</p>
          )}
          <button
            type="button"
            onClick={() => void handleAccept()}
            disabled={acceptMutation.isPending}
            style={{
              padding: '10px 16px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: acceptMutation.isPending ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-sans)',
              opacity: acceptMutation.isPending ? 0.7 : 1,
            }}
          >
            {acceptMutation.isPending ? 'Accepting...' : 'Accept invitation'}
          </button>
          <button
            type="button"
            onClick={() => void handleDecline()}
            disabled={declineMutation.isPending}
            style={{
              padding: '10px 16px',
              background: 'none',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
              color: 'var(--fg-muted)',
              cursor: declineMutation.isPending ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {declineMutation.isPending ? 'Declining...' : 'Decline'}
          </button>
        </div>
      )}
    </PageShell>
  )
}
