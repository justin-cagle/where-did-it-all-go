export type PrivacyMode = 'off' | 'partial_blur' | 'full_blur'

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const val = bytes / Math.pow(1024, i)
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`
}

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
