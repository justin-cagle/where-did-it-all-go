import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { CategoryOut } from '@/api/generated/model/categoryOut'
import { categoryColor } from '@/domain/transactions'

interface Props {
  categories: CategoryOut[]
  value: string | null
  onChange: (id: string | null) => void
  placeholder?: string
  disabled?: boolean
}

export function CategorySelect({
  categories,
  value,
  onChange,
  placeholder = 'Category',
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const selected = categories.find((c) => c.id === value) ?? null
  const parents = categories.filter((c) => !c.parent_id).sort((a, b) => a.sort_order - b.sort_order)
  const children = categories.filter((c) => !!c.parent_id)

  const lc = search.toLowerCase()
  const filtered = search ? categories.filter((c) => c.name.toLowerCase().includes(lc)) : null

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

  function select(id: string | null) {
    onChange(id)
    setOpen(false)
    setSearch('')
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          setOpen((o) => !o)
          setTimeout(() => inputRef.current?.focus(), 50)
        }}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '7px 10px',
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--bg-elevated)',
          color: selected ? 'var(--fg-primary)' : 'var(--fg-muted)',
          fontSize: 13,
          cursor: disabled ? 'not-allowed' : 'pointer',
          textAlign: 'left' as const,
          opacity: disabled ? 0.6 : 1,
        }}
      >
        {selected && (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: categoryColor(selected.color, selected.name),
              flexShrink: 0,
              display: 'inline-block',
            }}
          />
        )}
        <span
          style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {selected ? selected.name : placeholder}
        </span>
        <ChevronDown size={13} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 100,
            marginTop: 4,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            maxHeight: 280,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              padding: '8px 10px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              flexShrink: 0,
            }}
          >
            <Search size={12} style={{ color: 'var(--fg-muted)' }} />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              style={{
                flex: 1,
                border: 'none',
                background: 'none',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
          </div>

          <div style={{ overflowY: 'auto', flex: 1 }}>
            <button
              type="button"
              onClick={() => select(null)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 12px',
                textAlign: 'left' as const,
                background: 'none',
                border: 'none',
                fontSize: 12,
                color: 'var(--fg-muted)',
                cursor: 'pointer',
              }}
            >
              No category
            </button>

            {filtered ? (
              <>
                {filtered.length === 0 && (
                  <div
                    style={{
                      padding: '12px',
                      fontSize: 12,
                      color: 'var(--fg-muted)',
                      textAlign: 'center' as const,
                    }}
                  >
                    No categories found
                  </div>
                )}
                {filtered.map((cat) => {
                  const col = categoryColor(cat.color, cat.name)
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => select(cat.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        width: '100%',
                        padding: '8px 12px',
                        background:
                          value === cat.id
                            ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                            : 'none',
                        border: 'none',
                        fontSize: 13,
                        color: 'var(--fg-primary)',
                        cursor: 'pointer',
                        textAlign: 'left' as const,
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: col,
                          flexShrink: 0,
                        }}
                      />
                      {cat.name}
                    </button>
                  )
                })}
              </>
            ) : (
              parents.map((parent) => {
                const kids = children.filter((c) => c.parent_id === parent.id)
                const col = categoryColor(parent.color, parent.name)
                return (
                  <div key={parent.id}>
                    <button
                      type="button"
                      onClick={() => select(parent.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        width: '100%',
                        padding: '8px 12px',
                        background:
                          value === parent.id
                            ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                            : 'none',
                        border: 'none',
                        fontSize: 13,
                        color: 'var(--fg-primary)',
                        cursor: 'pointer',
                        textAlign: 'left' as const,
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: col,
                          flexShrink: 0,
                        }}
                      />
                      {parent.name}
                    </button>
                    {kids.map((child) => {
                      const childCol = categoryColor(child.color, child.name)
                      return (
                        <button
                          key={child.id}
                          type="button"
                          onClick={() => select(child.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            width: '100%',
                            padding: '7px 12px 7px 28px',
                            background:
                              value === child.id
                                ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
                                : 'none',
                            border: 'none',
                            fontSize: 12,
                            color: 'var(--fg-secondary)',
                            cursor: 'pointer',
                            textAlign: 'left' as const,
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: childCol,
                              flexShrink: 0,
                            }}
                          />
                          {child.name}
                        </button>
                      )
                    })}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
