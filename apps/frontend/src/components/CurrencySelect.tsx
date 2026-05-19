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
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        className="border-input bg-background ring-offset-background focus:ring-ring flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm focus:ring-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className={selected ? '' : 'text-muted-foreground'}>
          {selected ? `${selected.code} — ${selected.name}` : placeholder}
        </span>
        <ChevronDown className="h-4 w-4 opacity-50" />
      </button>

      {open && (
        <div className="bg-popover absolute z-50 mt-1 w-full rounded-md border shadow-md">
          <div className="flex items-center border-b px-3 py-2">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <input
              autoFocus
              className="placeholder:text-muted-foreground flex-1 bg-transparent text-sm outline-none"
              placeholder="Search currencies..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="max-h-60 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <div className="text-muted-foreground px-3 py-2 text-sm">No currencies found</div>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => select(c.code)}
                  className={`hover:bg-accent flex w-full items-center gap-2 px-3 py-2 text-sm ${
                    c.code === value ? 'bg-accent font-medium' : ''
                  }`}
                >
                  <span className="w-8 font-mono text-xs font-semibold">{c.code}</span>
                  <span className="text-muted-foreground">{c.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
