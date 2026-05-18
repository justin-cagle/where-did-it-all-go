import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGetReadOnlyApiV1AdminEmergencyReadOnlyGet,
  getGetReadOnlyApiV1AdminEmergencyReadOnlyGetQueryKey,
  useSetReadOnlyApiV1AdminEmergencyReadOnlyPost,
} from '@/api/generated/admin/admin'
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

const BLOCKS = [
  'All transaction creation and edits',
  'Account changes',
  'Budget, goal, debt plan edits',
  'SimpleFIN sync (paused)',
  'Classification pipeline',
  'File imports',
  'AI insight generation',
]

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

export function AdminEmergencyPage() {
  const qc = useQueryClient()
  const [stepUpFor, setStepUpFor] = useState<'enable' | 'disable' | null>(null)
  const [reasonText, setReasonText] = useState('')
  const [showReasonModal, setShowReasonModal] = useState(false)

  const { data: state } = useGetReadOnlyApiV1AdminEmergencyReadOnlyGet()
  const setReadOnly = useSetReadOnlyApiV1AdminEmergencyReadOnlyPost()

  async function doEnable() {
    await setReadOnly.mutateAsync({ data: { enabled: true, reason: reasonText } })
    await qc.invalidateQueries({ queryKey: getGetReadOnlyApiV1AdminEmergencyReadOnlyGetQueryKey() })
    setReasonText('')
    setShowReasonModal(false)
  }

  async function doDisable() {
    await setReadOnly.mutateAsync({ data: { enabled: false } })
    await qc.invalidateQueries({ queryKey: getGetReadOnlyApiV1AdminEmergencyReadOnlyGetQueryKey() })
  }

  const isEnabled = state?.enabled ?? false

  return (
    <div
      style={{
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 24,
        background: isEnabled ? `rgba(245,158,11,0.04)` : 'transparent',
        minHeight: '100%',
      }}
    >
      {stepUpFor === 'enable' && (
        <StepUpModal
          onSuccess={() => {
            setStepUpFor(null)
            setShowReasonModal(true)
          }}
          onCancel={() => setStepUpFor(null)}
        />
      )}
      {stepUpFor === 'disable' && (
        <StepUpModal
          onSuccess={async () => {
            setStepUpFor(null)
            await doDisable()
          }}
          onCancel={() => setStepUpFor(null)}
        />
      )}

      {/* Reason modal */}
      {showReasonModal && (
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
              width: 440,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Enable read-only mode</div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              Describe why you're enabling read-only mode. This reason is shown to all users.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <textarea
                value={reasonText}
                onChange={(e) => setReasonText(e.target.value)}
                rows={4}
                placeholder="e.g. Performing database maintenance..."
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  fontSize: 13,
                  background: A.bg,
                  border: `1px solid ${A.border}`,
                  color: A.fg,
                  outline: 'none',
                  resize: 'vertical',
                  fontFamily: 'inherit',
                }}
              />
              <div style={{ fontSize: 11, color: A.fgMuted, textAlign: 'right' }}>
                {reasonText.length} chars (min 10)
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowReasonModal(false)}
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
                disabled={reasonText.length < 10}
                onClick={doEnable}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: reasonText.length >= 10 ? A.danger : A.border,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: reasonText.length >= 10 ? 'pointer' : 'not-allowed',
                }}
              >
                Enable read-only mode
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h1
          style={{ fontSize: 20, fontWeight: 600, color: isEnabled ? A.warning : A.fg, margin: 0 }}
        >
          Emergency
        </h1>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>Read-only panic switch</p>
      </div>

      {/* State panel */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${isEnabled ? A.warning : A.border}`,
          borderRadius: 10,
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: isEnabled ? A.warning : A.success,
              flexShrink: 0,
              boxShadow: isEnabled ? `0 0 0 3px rgba(245,158,11,0.2)` : undefined,
              animation: isEnabled ? 'pulse 1.5s infinite' : undefined,
            }}
          />
          <style>{`@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }`}</style>
          <span style={{ fontSize: 15, fontWeight: 600, color: isEnabled ? A.warning : A.success }}>
            {isEnabled ? 'READ-ONLY MODE ACTIVE' : 'System operating normally'}
          </span>
        </div>

        {isEnabled ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingLeft: 20 }}>
            {state?.reason && (
              <div style={{ fontSize: 13, color: A.fg }}>Reason: {state.reason}</div>
            )}
            {state?.enabled_at && (
              <div style={{ fontSize: 13, color: A.fgMuted }}>
                Enabled: {relativeTime(state.enabled_at)}
              </div>
            )}
            <div style={{ fontSize: 13, color: A.fgMuted }}>All write operations are blocked.</div>
          </div>
        ) : (
          <div style={{ paddingLeft: 20, fontSize: 13, color: A.fgMuted }}>
            Read-only mode is not active. All writes and syncs are enabled.
          </div>
        )}
      </div>

      {/* What it blocks */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
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
          What read-only blocks
        </div>
        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          {BLOCKS.map((item) => (
            <li key={item} style={{ fontSize: 13, color: A.fgMuted, display: 'flex', gap: 8 }}>
              <span style={{ color: A.danger, flexShrink: 0 }}>—</span> {item}
            </li>
          ))}
        </ul>
        <div style={{ borderTop: `1px solid ${A.border}`, paddingTop: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: A.fgMuted, marginBottom: 6 }}>
            Does NOT block
          </div>
          {['Viewing all data', 'Admin panel access', 'Auth (login/logout)'].map((item) => (
            <div
              key={item}
              style={{ fontSize: 13, color: A.fgMuted, display: 'flex', gap: 8, marginBottom: 4 }}
            >
              <span style={{ color: A.success, flexShrink: 0 }}>+</span> {item}
            </div>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12 }}>
        {!isEnabled ? (
          <button
            onClick={() => setStepUpFor('enable')}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              cursor: 'pointer',
              background: 'transparent',
              border: `2px solid ${A.danger}`,
              color: A.danger,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            Enable read-only mode
          </button>
        ) : (
          <button
            onClick={() => setStepUpFor('disable')}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              cursor: 'pointer',
              background: 'transparent',
              border: `2px solid ${A.success}`,
              color: A.success,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            Disable read-only mode
          </button>
        )}
      </div>
    </div>
  )
}
