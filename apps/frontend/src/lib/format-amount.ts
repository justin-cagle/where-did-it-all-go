/**
 * formatAmount — the canonical money display function.
 *
 * Every component displaying a monetary amount goes through this function.
 * The data layer stores raw NUMERIC; all formatting is purely display-layer.
 *
 * Chain: locale format → privacy mode → returns string.
 *
 * Privacy modes (per DECISIONS.md R4E):
 *   off          — full formatted value
 *   full_blur    — ••••
 *   partial_blur — magnitude without exact value (e.g. $•,•••)
 *
 * Locale formats (per DECISIONS.md R6):
 *   1,234.56   — US/UK   (en-US, en-GB)
 *   1.234,56   — EU      (de-DE, es-ES)
 *   1 234,56   — French  (fr-FR)
 *   1'234.56   — Swiss   (de-CH)
 */

export type PrivacyMode = 'off' | 'full_blur' | 'partial_blur'

export interface FormatAmountOptions {
  /** BCP 47 locale string. Defaults to 'en-US'. Per-user preference, not household. */
  locale?: string
  /** ISO 4217 currency code. Defaults to 'USD'. */
  currency?: string
  /** Active privacy mode. Defaults to 'off'. */
  privacyMode?: PrivacyMode
  /** Use compact notation (1.2k, 5.3M) — for chart axis labels only. */
  compact?: boolean
}

export function formatAmount(amount: number | string, options: FormatAmountOptions = {}): string {
  const { locale = 'en-US', currency = 'USD', privacyMode = 'off', compact = false } = options

  if (privacyMode === 'full_blur') {
    return '••••'
  }

  const numeric = typeof amount === 'string' ? parseFloat(amount) : amount

  const formatter = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    ...(compact ? { notation: 'compact', maximumSignificantDigits: 3 } : {}),
  })

  if (privacyMode === 'partial_blur') {
    return formatter
      .formatToParts(numeric)
      .map((part) => {
        if (part.type === 'integer' || part.type === 'fraction') {
          return part.value.replace(/\d/g, '•')
        }
        return part.value
      })
      .join('')
  }

  return formatter.format(numeric)
}
