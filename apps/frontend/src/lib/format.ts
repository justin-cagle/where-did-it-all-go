export type PrivacyMode = 'off' | 'partial_blur' | 'full_blur'

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const val = bytes / Math.pow(1024, i)
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`
}

export interface FmtOptions {
  privacyMode?: PrivacyMode
  currency?: string
  isApproximate?: boolean
}

export function fmt(
  n: number,
  privacyOrOpts: PrivacyMode | FmtOptions = 'off',
  currency = 'USD'
): string {
  const opts: FmtOptions =
    typeof privacyOrOpts === 'string' ? { privacyMode: privacyOrOpts, currency } : privacyOrOpts
  const privacyMode = opts.privacyMode ?? 'off'
  const cur = opts.currency ?? currency

  if (privacyMode === 'full_blur') return '••••'

  const abs = Math.abs(n)
  const str = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: cur,
    maximumFractionDigits: 2,
  }).format(abs)

  if (privacyMode === 'partial_blur') return str.replace(/\d/g, '•')

  const sign = n < 0 ? '-' : ''
  const approx = opts.isApproximate ? '~' : ''
  return approx + sign + str
}
