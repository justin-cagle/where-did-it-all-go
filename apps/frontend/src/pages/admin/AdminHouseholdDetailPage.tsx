import { useParams } from 'react-router-dom'
import { useGetHouseholdApiV1AdminHouseholdsHouseholdIdGet } from '@/api/generated/admin/admin'

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

function RoleBadge({ role }: { role: string }) {
  const isOwner = role === 'owner'
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        padding: '1px 6px',
        borderRadius: 99,
        background: isOwner ? `rgba(59,130,246,0.15)` : 'rgba(107,114,128,0.15)',
        color: isOwner ? A.accent : A.fgMuted,
        textTransform: 'capitalize',
      }}
    >
      {role}
    </span>
  )
}

export function AdminHouseholdDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: household, isLoading } = useGetHouseholdApiV1AdminHouseholdsHouseholdIdGet(id ?? '')

  if (isLoading || !household) {
    return <div style={{ padding: 32, color: A.fgMuted }}>Loading...</div>
  }

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 700 }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>
            {household.name}
          </h1>
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
            {household.visibility_mode}
          </span>
        </div>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
          {household.member_count} member{household.member_count !== 1 ? 's' : ''} &middot;{' '}
          {household.account_count} account{household.account_count !== 1 ? 's' : ''}
        </p>
      </div>

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
            display: 'grid',
            gridTemplateColumns: '1fr 200px 80px 100px',
            padding: '10px 16px',
            borderBottom: `1px solid ${A.border}`,
          }}
        >
          {['Name', 'Email', 'Role', 'Last seen'].map((h) => (
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
        {household.members.length === 0 ? (
          <div style={{ padding: '20px 16px', fontSize: 13, color: A.fgMuted }}>No members</div>
        ) : (
          household.members.map((m, i) => (
            <div
              key={m.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 200px 80px 100px',
                padding: '12px 16px',
                borderTop: i === 0 ? 'none' : `1px solid ${A.border}`,
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 500, color: A.fg }}>{m.display_name}</span>
              <span
                style={{
                  fontSize: 13,
                  color: A.fgMuted,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {m.email}
              </span>
              <span>
                <RoleBadge role="member" />
              </span>
              <span style={{ fontSize: 13, color: A.fgMuted }}>{relativeTime(m.created_at)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
