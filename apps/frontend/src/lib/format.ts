export type PrivacyMode = 'off' | 'partial_blur' | 'full_blur'

export function fmt(n: number, privacyMode: PrivacyMode = 'off', currency = 'USD'): string {
  if (privacyMode === 'full_blur') return '••••'

  const abs = Math.abs(n)
  const str = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(abs)

  if (privacyMode === 'partial_blur') return str.replace(/\d/g, '•')

  return (n < 0 ? '-' : '') + str
}
