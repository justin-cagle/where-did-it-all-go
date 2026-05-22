import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { useListCurrenciesApiV1CurrenciesGet } from '@/api/generated/platform/platform'

interface Props {
  value: string
  onChange: (code: string) => void
  placeholder?: string
  disabled?: boolean
}

export function CurrencySelect({
  value,
  onChange,
  placeholder = 'Currency',
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  const { data: currencies = [] } = useListCurrenciesApiV1CurrenciesGet({
    query: { staleTime: 24 * 60 * 60 * 1000 },
  })

  const selected = currencies.find((c) => c.code === value) ?? null
  const lc = search.toLowerCase()
  const filtered = search
    ? currencies.filter(
        (c) => c.code.toLowerCase().includes(lc) || c.name.toLowerCase().includes(lc)
      )
    : currencies

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  function select(code: string) {
    onChange(code)
    setOpen(false)
    setSearch('')
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--bg-primary)',
          color: selected ? 'var(--fg-primary)' : 'var(--fg-muted)',
          fontSize: 14,
          fontFamily: 'var(--font-sans)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          gap: 8,
        }}
      >
        <span>{selected ? `${selected.code} — ${selected.name}` : placeholder}</span>
        <ChevronDown style={{ width: 16, height: 16, flexShrink: 0, opacity: 0.5 }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 50,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            boxShadow: 'var(--shadow)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <Search style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--fg-muted)' }} />
            <input
              autoFocus
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                fontSize: 13,
                color: 'var(--fg-primary)',
                fontFamily: 'var(--font-sans)',
              }}
              placeholder="Search currencies..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div style={{ maxHeight: 240, overflowY: 'auto', padding: '4px 0' }}>
            {filtered.length === 0 ? (
              <div style={{ padding: '8px 12px', fontSize: 13, color: 'var(--fg-muted)' }}>
                No currencies found
              </div>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => select(c.code)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '8px 12px',
                    background:
                      c.code === value
                        ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                        : 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 13,
                    color: 'var(--fg-primary)',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  <span
                    style={{
                      width: 32,
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    {c.code}
                  </span>
                  <span style={{ color: 'var(--fg-muted)' }}>{c.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
