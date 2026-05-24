import { useRef, useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { GripVertical, Lock, Pencil, Plus, Archive, X } from 'lucide-react'
import type { CategoryOut } from '@/api/generated/model/categoryOut'
import {
  useCreateCategoryApiV1HouseholdsHouseholdIdCategoriesPost,
  useUpdateCategoryApiV1HouseholdsHouseholdIdCategoriesCategoryIdPatch,
  useArchiveCategoryApiV1HouseholdsHouseholdIdCategoriesCategoryIdDelete,
  useReorderCategoriesApiV1HouseholdsHouseholdIdCategoriesReorderPost,
  getListCategoriesApiV1HouseholdsHouseholdIdCategoriesGetQueryKey,
} from '@/api/generated/classification/classification'
import { categoryColor } from '@/domain/transactions'

const PRESETS = ['#6366f1', '#22c55e', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']

interface Props {
  householdId: string
  categories: CategoryOut[]
  qc: QueryClient
}

const BUDGET_ROLE_OPTIONS = ['needs', 'wants', 'savings', 'uncategorized'] as const
type BudgetRole = (typeof BUDGET_ROLE_OPTIONS)[number]

function BudgetRoleBadge({ role, onClick }: { role: string; onClick?: () => void }) {
  if (role === 'uncategorized') return null
  const styles: Record<string, { bg: string; color: string }> = {
    needs: {
      bg: 'color-mix(in oklch, var(--info, #3b82f6) 15%, transparent)',
      color: 'var(--info, #3b82f6)',
    },
    wants: {
      bg: 'color-mix(in oklch, #8b5cf6 15%, transparent)',
      color: '#8b5cf6',
    },
    savings: {
      bg: 'color-mix(in oklch, var(--success) 15%, transparent)',
      color: 'var(--success)',
    },
  }
  const s = styles[role]
  if (!s) return null
  return (
    <span
      onClick={onClick}
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '1px 7px',
        borderRadius: 99,
        background: s.bg,
        color: s.color,
        letterSpacing: '0.04em',
        textTransform: 'uppercase' as const,
        cursor: onClick ? 'pointer' : 'default',
        flexShrink: 0,
      }}
    >
      {role}
    </span>
  )
}

interface EditState {
  id: string
  value: string
  budgetRole: BudgetRole
  showRolePicker: boolean
}

interface ColorPickerProps {
  value: string | null
  onChange: (hex: string | null) => void
  onClose: () => void
}

function ColorPicker({ value, onChange, onClose }: ColorPickerProps) {
  const [hex, setHex] = useState(value ?? '')

  return (
    <div
      style={{
        position: 'absolute',
        zIndex: 50,
        top: '100%',
        left: 0,
        marginTop: 4,
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
              onClose()
            }}
            style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              background: p,
              border: value === p ? '2px solid var(--fg-primary)' : '2px solid transparent',
              cursor: 'pointer',
              padding: 0,
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
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
              onClose()
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
      <button
        type="button"
        onClick={() => {
          onChange(null)
          onClose()
        }}
        style={{
          marginTop: 8,
          width: '100%',
          padding: '4px',
          fontSize: 11,
          color: 'var(--fg-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        Clear color
      </button>
    </div>
  )
}

interface AddCategoryFormProps {
  householdId: string
  parentId: string | null
  onDone: () => void
  qc: QueryClient
}

function AddCategoryForm({ householdId, parentId, onDone, qc }: AddCategoryFormProps) {
  const [name, setName] = useState('')
  const [color, setColor] = useState<string | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)

  const create = useCreateCategoryApiV1HouseholdsHouseholdIdCategoriesPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListCategoriesApiV1HouseholdsHouseholdIdCategoriesGetQueryKey(householdId),
        })
        onDone()
      },
    },
  })

  function submit() {
    const trimmed = name.trim()
    if (!trimmed) return
    create.mutate({
      householdId,
      data: { name: trimmed, parent_id: parentId, color: color ?? undefined },
    })
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        background: 'color-mix(in oklch, var(--accent) 5%, transparent)',
        borderRadius: 8,
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setPickerOpen((o) => !o)}
          style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: color ?? 'var(--border)',
            border: '1px solid var(--border)',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
          }}
        />
        {pickerOpen && (
          <ColorPicker value={color} onChange={setColor} onClose={() => setPickerOpen(false)} />
        )}
      </div>
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit()
          if (e.key === 'Escape') onDone()
        }}
        placeholder="Category name"
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
        onClick={submit}
        disabled={!name.trim() || create.isPending}
        style={{
          padding: '3px 8px',
          fontSize: 12,
          background: 'var(--accent)',
          color: 'var(--accent-fg)',
          border: 'none',
          borderRadius: 6,
          cursor: name.trim() && !create.isPending ? 'pointer' : 'not-allowed',
          opacity: name.trim() && !create.isPending ? 1 : 0.5,
        }}
      >
        Add
      </button>
      <button
        type="button"
        onClick={onDone}
        style={{
          padding: 3,
          background: 'none',
          border: 'none',
          color: 'var(--fg-muted)',
          cursor: 'pointer',
        }}
      >
        <X size={13} />
      </button>
    </div>
  )
}

export function CategoriesTab({ householdId, categories, qc }: Props) {
  const [editing, setEditing] = useState<EditState | null>(null)
  const [colorPickerFor, setColorPickerFor] = useState<string | null>(null)
  const [addingChildOf, setAddingChildOf] = useState<string | null>(null)
  const [addingRoot, setAddingRoot] = useState(false)
  const [archiveConfirm, setArchiveConfirm] = useState<string | null>(null)
  const [localParentOrder, setLocalParentOrder] = useState<CategoryOut[] | null>(null)
  const [localChildOrders, setLocalChildOrders] = useState<Record<string, CategoryOut[]>>({})
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dragGroupRef = useRef<string | null>(null)
  const dragIndexRef = useRef<number | null>(null)

  const update = useUpdateCategoryApiV1HouseholdsHouseholdIdCategoriesCategoryIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListCategoriesApiV1HouseholdsHouseholdIdCategoriesGetQueryKey(householdId),
        })
      },
    },
  })

  const archive = useArchiveCategoryApiV1HouseholdsHouseholdIdCategoriesCategoryIdDelete({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListCategoriesApiV1HouseholdsHouseholdIdCategoriesGetQueryKey(householdId),
        })
        setArchiveConfirm(null)
        setLocalParentOrder(null)
        setLocalChildOrders({})
      },
    },
  })

  const reorder = useReorderCategoriesApiV1HouseholdsHouseholdIdCategoriesReorderPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListCategoriesApiV1HouseholdsHouseholdIdCategoriesGetQueryKey(householdId),
        })
        setLocalParentOrder(null)
        setLocalChildOrders({})
      },
    },
  })

  const systemParents = categories
    .filter((c) => !c.parent_id && c.system)
    .sort((a, b) => a.sort_order - b.sort_order)

  const serverHouseholdParents = categories
    .filter((c) => !c.parent_id && !c.system)
    .sort((a, b) => a.sort_order - b.sort_order)

  const householdParents = localParentOrder ?? serverHouseholdParents

  const serverChildrenOf = (parentId: string) =>
    categories.filter((c) => c.parent_id === parentId).sort((a, b) => a.sort_order - b.sort_order)

  const childrenOf = (parentId: string) => localChildOrders[parentId] ?? serverChildrenOf(parentId)

  function startEdit(cat: CategoryOut) {
    if (!cat.renameable) return
    setEditing({
      id: cat.id,
      value: cat.name,
      budgetRole: (cat.budget_role as BudgetRole) ?? 'uncategorized',
      showRolePicker: false,
    })
  }

  function handleNameChange(val: string) {
    if (!editing) return
    setEditing({ ...editing, value: val })
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (val.trim()) {
        update.mutate({ householdId, categoryId: editing.id, data: { name: val.trim() } })
      }
    }, 400)
  }

  function handleBudgetRoleChange(catId: string, role: BudgetRole) {
    update.mutate({ householdId, categoryId: catId, data: { budget_role: role } })
    if (editing?.id === catId) {
      setEditing({ ...editing, budgetRole: role, showRolePicker: false })
    }
  }

  function commitEdit() {
    if (!editing) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const val = editing.value.trim()
    if (val) {
      update.mutate({ householdId, categoryId: editing.id, data: { name: val } })
    }
    setEditing(null)
  }

  function cancelEdit() {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setEditing(null)
  }

  function updateColor(catId: string, color: string | null) {
    update.mutate({ householdId, categoryId: catId, data: { color: color ?? undefined } })
    setColorPickerFor(null)
  }

  // group is 'parents' for top-level household cats, or parentId for children
  function handleDragStart(group: string, index: number) {
    dragGroupRef.current = group
    dragIndexRef.current = index
  }

  function handleDragOver(e: React.DragEvent, group: string, index: number) {
    e.preventDefault()
    if (dragGroupRef.current !== group) return
    const from = dragIndexRef.current
    if (from === null || from === index) return
    if (group === 'parents') {
      const next = [...householdParents]
      const [moved] = next.splice(from, 1)
      if (moved === undefined) return
      next.splice(index, 0, moved)
      dragIndexRef.current = index
      setLocalParentOrder(next)
    } else {
      const current = childrenOf(group)
      const next = [...current]
      const [moved] = next.splice(from, 1)
      if (moved === undefined) return
      next.splice(index, 0, moved)
      dragIndexRef.current = index
      setLocalChildOrders((prev) => ({ ...prev, [group]: next }))
    }
  }

  function handleDrop(group: string) {
    dragGroupRef.current = null
    dragIndexRef.current = null
    if (group === 'parents') {
      reorder.mutate({
        householdId,
        data: {
          items: householdParents.map((c, i) => ({ category_id: c.id, sort_order: i })),
        },
      })
    } else {
      const kids = childrenOf(group)
      reorder.mutate({
        householdId,
        data: {
          items: kids.map((c, i) => ({ category_id: c.id, sort_order: i })),
        },
      })
    }
  }

  function handleDragEnd() {
    dragGroupRef.current = null
    dragIndexRef.current = null
  }

  function renderRow(cat: CategoryOut, group: string, groupIndex: number, indent = false) {
    const col = categoryColor(cat.color, cat.name)
    const isEditing = editing?.id === cat.id
    const showColorPicker = colorPickerFor === cat.id
    const draggable = !cat.system

    return (
      <div
        key={cat.id}
        draggable={draggable}
        onDragStart={draggable ? () => handleDragStart(group, groupIndex) : undefined}
        onDragOver={draggable ? (e) => handleDragOver(e, group, groupIndex) : undefined}
        onDrop={draggable ? () => handleDrop(group) : undefined}
        onDragEnd={draggable ? handleDragEnd : undefined}
      >
        <div
          className="cat-row"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: `7px ${indent ? 32 : 12}px 7px ${indent ? 32 : 12}px`,
            borderRadius: 8,
            position: 'relative',
          }}
        >
          {/* Drag handle */}
          <div
            className="cat-drag-handle"
            style={{
              cursor: draggable ? 'grab' : 'default',
              color: 'var(--fg-muted)',
              display: 'flex',
              alignItems: 'center',
              opacity: draggable ? 0 : 0,
              transition: 'opacity 0.1s',
              flexShrink: 0,
              visibility: draggable ? 'visible' : 'hidden',
            }}
          >
            <GripVertical size={14} />
          </div>

          {/* Color dot */}
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <button
              type="button"
              title="Change color"
              onClick={() => setColorPickerFor(showColorPicker ? null : cat.id)}
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: col,
                border: 'none',
                cursor: 'pointer',
                padding: 0,
              }}
            />
            {showColorPicker && (
              <ColorPicker
                value={cat.color ?? null}
                onChange={(hex) => updateColor(cat.id, hex)}
                onClose={() => setColorPickerFor(null)}
              />
            )}
          </div>

          {/* Name / edit input */}
          {isEditing ? (
            <input
              autoFocus
              value={editing.value}
              onChange={(e) => handleNameChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit()
                if (e.key === 'Escape') cancelEdit()
              }}
              onBlur={commitEdit}
              style={{
                flex: 1,
                border: 'none',
                borderBottom: '1px solid var(--accent)',
                background: 'none',
                color: 'var(--fg-primary)',
                fontSize: indent ? 12 : 13,
                fontWeight: indent ? 400 : 500,
                outline: 'none',
                padding: '1px 0',
              }}
            />
          ) : (
            <span
              onClick={() => startEdit(cat)}
              style={{
                flex: 1,
                fontSize: indent ? 12 : 13,
                fontWeight: indent ? 400 : 500,
                color: indent ? 'var(--fg-secondary)' : 'var(--fg-primary)',
                cursor: cat.renameable ? 'text' : 'default',
              }}
            >
              {cat.name}
            </span>
          )}

          {/* Budget role badge / picker */}
          {isEditing ? (
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <BudgetRoleBadge
                role={editing.budgetRole}
                onClick={() => setEditing({ ...editing, showRolePicker: !editing.showRolePicker })}
              />
              {editing.budgetRole === 'uncategorized' && (
                <button
                  type="button"
                  onClick={() =>
                    setEditing({ ...editing, showRolePicker: !editing.showRolePicker })
                  }
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-muted)',
                    background: 'none',
                    border: '1px dashed var(--border)',
                    borderRadius: 99,
                    padding: '1px 7px',
                    cursor: 'pointer',
                  }}
                >
                  set role
                </button>
              )}
              {editing.showRolePicker && (
                <div
                  style={{
                    position: 'absolute',
                    zIndex: 50,
                    top: '100%',
                    left: 0,
                    marginTop: 4,
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                    overflow: 'hidden',
                    minWidth: 130,
                  }}
                >
                  {BUDGET_ROLE_OPTIONS.map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => handleBudgetRoleChange(cat.id, role)}
                      style={{
                        display: 'block',
                        width: '100%',
                        padding: '6px 12px',
                        textAlign: 'left' as const,
                        fontSize: 12,
                        background:
                          editing.budgetRole === role
                            ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                            : 'none',
                        border: 'none',
                        color: 'var(--fg-primary)',
                        cursor: 'pointer',
                      }}
                    >
                      {role}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <BudgetRoleBadge role={cat.budget_role ?? 'uncategorized'} />
          )}

          {/* System badge */}
          {cat.system && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                color: 'var(--fg-muted)',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '1px 5px',
              }}
            >
              system
            </span>
          )}

          {/* Lock icon */}
          {cat.system && <Lock size={11} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />}

          {/* Hover actions */}
          <div
            className="cat-actions"
            style={{
              display: 'flex',
              gap: 2,
              opacity: 0,
              transition: 'opacity 0.1s',
            }}
          >
            {cat.renameable && (
              <button
                type="button"
                title="Edit name"
                onClick={() => startEdit(cat)}
                style={actionBtnStyle}
              >
                <Pencil size={12} />
              </button>
            )}
            {!indent && !cat.system && (
              <button
                type="button"
                title="Add child category"
                onClick={() => setAddingChildOf(cat.id)}
                style={actionBtnStyle}
              >
                <Plus size={12} />
              </button>
            )}
            {cat.deletable && (
              <button
                type="button"
                title="Archive"
                onClick={() => setArchiveConfirm(cat.id)}
                style={{ ...actionBtnStyle, color: 'var(--danger)' }}
              >
                <Archive size={12} />
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <style>{`
        .cat-row:hover .cat-actions { opacity: 1 !important; }
        .cat-row:hover .cat-drag-handle { opacity: 1 !important; }
        .cat-row:hover { background: color-mix(in oklch, var(--fg-primary) 4%, transparent); }
      `}</style>

      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        {/* System categories — fixed, non-draggable */}
        {systemParents.map((cat, pi) => (
          <div key={cat.id}>
            {pi > 0 && <div style={{ height: 1, background: 'var(--border)' }} />}
            {renderRow(cat, 'system', pi)}
          </div>
        ))}

        {/* Household categories — draggable */}
        {householdParents.map((parent, pi) => {
          const kids = childrenOf(parent.id)
          const hasDivider = systemParents.length > 0 || pi > 0
          return (
            <div key={parent.id}>
              {hasDivider && <div style={{ height: 1, background: 'var(--border)' }} />}
              {renderRow(parent, 'parents', pi)}
              {kids.map((child, ci) => renderRow(child, parent.id, ci, true))}
              {addingChildOf === parent.id && (
                <div style={{ padding: '4px 32px 8px' }}>
                  <AddCategoryForm
                    householdId={householdId}
                    parentId={parent.id}
                    onDone={() => setAddingChildOf(null)}
                    qc={qc}
                  />
                </div>
              )}
            </div>
          )
        })}

        {addingRoot ? (
          <div
            style={{
              padding: '4px 12px 8px',
              borderTop:
                systemParents.length > 0 || householdParents.length > 0
                  ? '1px solid var(--border)'
                  : 'none',
            }}
          >
            <AddCategoryForm
              householdId={householdId}
              parentId={null}
              onDone={() => setAddingRoot(false)}
              qc={qc}
            />
          </div>
        ) : (
          <div
            style={{
              borderTop:
                systemParents.length > 0 || householdParents.length > 0
                  ? '1px solid var(--border)'
                  : 'none',
              padding: '8px 12px',
            }}
          >
            <button
              type="button"
              onClick={() => setAddingRoot(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: 'var(--accent)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px 0',
              }}
            >
              <Plus size={13} />
              Add category
            </button>
          </div>
        )}
      </div>

      {/* Archive confirm */}
      {archiveConfirm &&
        (() => {
          const cat = categories.find((c) => c.id === archiveConfirm)
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
              onClick={() => setArchiveConfirm(null)}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 24,
                  width: 360,
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
                  Archive &ldquo;{cat?.name}&rdquo;?
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px' }}>
                  Archived categories are hidden from the UI but transactions keep their
                  categorization.
                </p>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => setArchiveConfirm(null)}
                    style={cancelBtnStyle}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={archive.isPending}
                    onClick={() => archive.mutate({ householdId, categoryId: archiveConfirm })}
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
  justifyContent: 'center',
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
