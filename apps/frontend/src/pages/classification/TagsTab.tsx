import { useRef, useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { Pencil, Trash2 } from 'lucide-react'
import type { TagOut } from '@/api/generated/model/tagOut'
import {
  useCreateTagApiV1HouseholdsHouseholdIdTagsPost,
  useUpdateTagApiV1HouseholdsHouseholdIdTagsTagIdPatch,
  useArchiveTagApiV1HouseholdsHouseholdIdTagsTagIdDelete,
  getListTagsApiV1HouseholdsHouseholdIdTagsGetQueryKey,
} from '@/api/generated/classification/classification'

const PRESETS = ['#6366f1', '#22c55e', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']

interface Props {
  householdId: string
  tags: TagOut[]
  qc: QueryClient
}

function ColorDotPicker({
  value,
  onChange,
}: {
  value: string | null
  onChange: (hex: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [hex, setHex] = useState(value ?? '')
  const col = value ?? '#6366f1'

  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: col,
          border: '1px solid var(--border)',
          cursor: 'pointer',
          padding: 0,
          flexShrink: 0,
        }}
      />
      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: 4,
            zIndex: 50,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: 12,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            width: 200,
          }}
        >
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => {
                  onChange(p)
                  setHex(p)
                  setOpen(false)
                }}
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  background: p,
                  border: col === p ? '2px solid var(--fg-primary)' : '2px solid transparent',
                  cursor: 'pointer',
                  padding: 0,
                }}
              />
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              value={hex}
              onChange={(e) => setHex(e.target.value)}
              placeholder="#rrggbb"
              maxLength={7}
              style={{
                flex: 1,
                padding: '5px 8px',
                fontSize: 12,
                fontFamily: 'var(--font-mono, monospace)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                outline: 'none',
              }}
            />
            <button
              type="button"
              onClick={() => {
                if (/^#[0-9a-fA-F]{6}$/.test(hex)) {
                  onChange(hex)
                  setOpen(false)
                }
              }}
              style={{
                padding: '5px 8px',
                fontSize: 12,
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function TagsTab({ householdId, tags, qc }: Props) {
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState<string>('#6366f1')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const create = useCreateTagApiV1HouseholdsHouseholdIdTagsPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListTagsApiV1HouseholdsHouseholdIdTagsGetQueryKey(householdId),
        })
        setNewName('')
        setNewColor('#6366f1')
      },
    },
  })

  const update = useUpdateTagApiV1HouseholdsHouseholdIdTagsTagIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListTagsApiV1HouseholdsHouseholdIdTagsGetQueryKey(householdId),
        })
      },
    },
  })

  const archive = useArchiveTagApiV1HouseholdsHouseholdIdTagsTagIdDelete({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListTagsApiV1HouseholdsHouseholdIdTagsGetQueryKey(householdId),
        })
        setDeleteConfirm(null)
      },
    },
  })

  function submitCreate() {
    const trimmed = newName.trim()
    if (!trimmed) return
    create.mutate({ householdId, data: { name: trimmed, color: newColor } })
  }

  function startEdit(tag: TagOut) {
    setEditingId(tag.id)
    setEditValue(tag.name)
  }

  function handleEditChange(val: string, tagId: string) {
    setEditValue(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (val.trim()) {
        update.mutate({ householdId, tagId, data: { name: val.trim() } })
      }
    }, 400)
  }

  function commitEdit(tagId: string) {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (editValue.trim()) {
      update.mutate({ householdId, tagId, data: { name: editValue.trim() } })
    }
    setEditingId(null)
  }

  function cancelEdit() {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setEditingId(null)
  }

  return (
    <>
      {/* Inline create */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          marginBottom: 12,
        }}
      >
        <ColorDotPicker value={newColor} onChange={setNewColor} />
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitCreate()
          }}
          placeholder="New tag name..."
          style={{
            flex: 1,
            border: 'none',
            background: 'none',
            color: 'var(--fg-primary)',
            fontSize: 13,
            outline: 'none',
          }}
        />
        <button
          type="button"
          onClick={submitCreate}
          disabled={!newName.trim() || create.isPending}
          style={{
            padding: '5px 12px',
            fontSize: 12,
            fontWeight: 500,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            borderRadius: 6,
            cursor: newName.trim() && !create.isPending ? 'pointer' : 'not-allowed',
            opacity: newName.trim() && !create.isPending ? 1 : 0.5,
          }}
        >
          Add
        </button>
      </div>

      {/* Tag list */}
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        {tags.length === 0 && (
          <div
            style={{
              padding: '20px 16px',
              fontSize: 13,
              color: 'var(--fg-muted)',
              textAlign: 'center',
            }}
          >
            No tags yet. Add one above.
          </div>
        )}
        {tags.map((tag, i) => {
          const isEditing = editingId === tag.id
          return (
            <div key={tag.id}>
              {i > 0 && <div style={{ height: 1, background: 'var(--border)' }} />}
              <div
                className="tag-row"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 12px',
                  position: 'relative',
                }}
              >
                {/* Color dot */}
                <ColorDotPicker
                  value={tag.color ?? null}
                  onChange={(hex) =>
                    update.mutate({ householdId, tagId: tag.id, data: { color: hex } })
                  }
                />

                {/* Name */}
                {isEditing ? (
                  <input
                    autoFocus
                    value={editValue}
                    onChange={(e) => handleEditChange(e.target.value, tag.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitEdit(tag.id)
                      if (e.key === 'Escape') cancelEdit()
                    }}
                    onBlur={() => commitEdit(tag.id)}
                    style={{
                      flex: 1,
                      border: 'none',
                      borderBottom: '1px solid var(--accent)',
                      background: 'none',
                      color: 'var(--fg-primary)',
                      fontSize: 13,
                      outline: 'none',
                      padding: '1px 0',
                    }}
                  />
                ) : (
                  <span
                    style={{ flex: 1, fontSize: 13, color: 'var(--fg-primary)', cursor: 'text' }}
                    onClick={() => startEdit(tag)}
                  >
                    {tag.name}
                  </span>
                )}

                {/* Actions */}
                <div
                  className="tag-actions"
                  style={{ display: 'flex', gap: 2, opacity: 0, transition: 'opacity 0.1s' }}
                >
                  <button type="button" onClick={() => startEdit(tag)} style={actionBtnStyle}>
                    <Pencil size={12} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(tag.id)}
                    style={{ ...actionBtnStyle, color: 'var(--danger)' }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <style>{`.tag-row:hover .tag-actions { opacity: 1 !important; } .tag-row:hover { background: color-mix(in oklch, var(--fg-primary) 4%, transparent); }`}</style>

      {/* Delete confirm */}
      {deleteConfirm &&
        (() => {
          const tag = tags.find((t) => t.id === deleteConfirm)
          return (
            <div
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 200,
              }}
              onClick={() => setDeleteConfirm(null)}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 24,
                  width: 340,
                  boxShadow: 'var(--shadow)',
                }}
              >
                <h2
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'var(--fg-primary)',
                    margin: '0 0 8px',
                  }}
                >
                  Archive &ldquo;{tag?.name}&rdquo;?
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px' }}>
                  Transactions with this tag will keep it, but the tag won&apos;t appear in pickers.
                </p>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(null)}
                    style={cancelBtnStyle}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={archive.isPending}
                    onClick={() => archive.mutate({ householdId, tagId: deleteConfirm })}
                    style={dangerBtnStyle}
                  >
                    {archive.isPending ? 'Archiving...' : 'Archive'}
                  </button>
                </div>
              </div>
            </div>
          )
        })()}
    </>
  )
}

const actionBtnStyle: React.CSSProperties = {
  padding: 4,
  background: 'none',
  border: 'none',
  color: 'var(--fg-secondary)',
  cursor: 'pointer',
  borderRadius: 4,
  display: 'flex',
  alignItems: 'center',
}

const cancelBtnStyle: React.CSSProperties = {
  padding: '7px 14px',
  fontSize: 13,
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--fg-secondary)',
  cursor: 'pointer',
}

const dangerBtnStyle: React.CSSProperties = {
  padding: '7px 14px',
  fontSize: 13,
  fontWeight: 500,
  background: 'var(--danger)',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  cursor: 'pointer',
}
