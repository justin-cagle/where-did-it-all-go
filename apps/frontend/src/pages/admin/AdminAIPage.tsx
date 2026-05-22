import { useHousehold } from '@/hooks/use-household'
import { InsightsSettingsPage } from '@/pages/settings/InsightsSettingsPage'

const A = {
  fgMuted: '#6b7280',
}

export function AdminAIPage() {
  const { householdId } = useHousehold()

  if (!householdId) {
    return (
      <div style={{ padding: '32px 40px' }}>
        <div style={{ fontSize: 13, color: A.fgMuted }}>
          Admin account must be assigned to a household before configuring AI providers.
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '32px 40px' }}>
      <InsightsSettingsPage />
    </div>
  )
}
