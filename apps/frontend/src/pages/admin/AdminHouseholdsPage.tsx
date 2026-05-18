import { useNavigate } from 'react-router-dom'
import { useListHouseholdsApiV1AdminHouseholdsGet } from '@/api/generated/admin/admin'

const A = {
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
}

function relativeTime(iso: string): string {
  try {
    const diffHr = (Date.now() - new Date(iso).getTime()) / 3_600_000
    if (diffHr < 24) return `${Math.floor(diffHr)}h ago`
    return `${Math.floor(diffHr / 24)}d ago`
  } catch {
    return iso
  }
}

export function AdminHouseholdsPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useListHouseholdsApiV1AdminHouseholdsGet()
  const households = data?.items ?? []

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>Households</h1>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
          All households on this instance
        </p>
      </div>

      {isLoading ? (
        <div style={{ color: A.fgMuted, fontSize: 13 }}>Loading...</div>
      ) : (
        <div
          style={{
            background: A.bgRaised,
            border: `1px solid ${A.border}`,
            borderRadius: 10,
            overflow: 'hidden',
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 80px 80px 120px',
              gap: 0,
              padding: '10px 16px',
              borderBottom: `1px solid ${A.border}`,
            }}
          >
            {['Name', 'Visibility', 'Members', 'Accounts', 'Created'].map((h) => (
              <div
                key={h}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: A.fgMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {h}
              </div>
            ))}
          </div>
          {households.length === 0 ? (
            <div style={{ padding: '20px 16px', fontSize: 13, color: A.fgMuted }}>
              No households
            </div>
          ) : (
            households.map((h, i) => (
              <div
                key={h.id}
                onClick={() => navigate(`/admin/households/${h.id}`)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 120px 80px 80px 120px',
                  gap: 0,
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderTop: i === 0 ? 'none' : `1px solid ${A.border}`,
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.02)'
                }}
                onMouseLeave={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'transparent'
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 500, color: A.fg }}>{h.name}</span>
                <span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 99,
                      background: `rgba(59,130,246,0.12)`,
                      color: A.accent,
                    }}
                  >
                    {h.visibility_mode}
                  </span>
                </span>
                <span style={{ fontSize: 13, color: A.fg }}>{h.member_count}</span>
                <span style={{ fontSize: 13, color: A.fg }}>{h.account_count}</span>
                <span style={{ fontSize: 13, color: A.fgMuted }}>{relativeTime(h.created_at)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
