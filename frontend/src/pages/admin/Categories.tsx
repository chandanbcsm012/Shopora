import { useEffect, useMemo, useState, type FormEvent } from 'react'
import * as catalogApi from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Category } from '../../api/types'
import { Alert, Button, Card, ConfirmDialog, EmptyState, ImageUploader, Input, Skeleton } from '../../components/ui'
import { slugify } from '../../lib/slugify'

interface FormState {
  name: string
  slug: string
  slugTouched: boolean
  parentId: string
  imageUrl: string | null
}

const EMPTY_FORM: FormState = { name: '', slug: '', slugTouched: false, parentId: '', imageUrl: null }

export default function Categories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const categoryNameById = useMemo(() => new Map(categories.map((c) => [c.id, c.name])), [categories])

  function loadCategories() {
    setIsLoading(true)
    setError(null)
    return catalogApi
      .listCategories()
      .then(setCategories)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load categories'))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    void loadCategories()
  }, [])

  function openCreateForm() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setIsFormOpen(true)
  }

  function openEditForm(category: Category) {
    setEditingId(category.id)
    setForm({
      name: category.name,
      slug: category.slug,
      slugTouched: true,
      parentId: category.parent_id ?? '',
      imageUrl: category.image_url,
    })
    setFormError(null)
    setIsFormOpen(true)
  }

  function closeForm() {
    setIsFormOpen(false)
    setFormError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    setIsSaving(true)
    const payload = {
      name: form.name,
      slug: form.slug,
      parent_id: form.parentId || null,
      image_url: form.imageUrl,
    }
    try {
      if (editingId) {
        const updated = await catalogApi.updateCategory(editingId, payload)
        setCategories((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      } else {
        const created = await catalogApi.createCategory(payload)
        setCategories((prev) => [...prev, created])
      }
      closeForm()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to save category')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await catalogApi.deleteCategory(deleteTarget.id)
      setCategories((prev) => prev.filter((c) => c.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Failed to delete category')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-medium text-gray-900">Categories</h2>
        {!isFormOpen && <Button size="sm" onClick={openCreateForm}>Add category</Button>}
      </div>

      {isFormOpen && (
        <Card className="mb-6 p-4">
          <h3 className="mb-4 text-sm font-semibold text-gray-900">
            {editingId ? 'Edit category' : 'New category'}
          </h3>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Name"
              required
              value={form.name}
              onChange={(e) => {
                const name = e.target.value
                setForm((prev) => ({
                  ...prev,
                  name,
                  slug: prev.slugTouched ? prev.slug : slugify(name),
                }))
              }}
            />
            <Input
              label="Slug"
              required
              value={form.slug}
              onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value, slugTouched: true }))}
              hint="Auto-suggested from the name; edit freely."
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="category-parent" className="text-sm font-medium text-gray-700">
                Parent category
              </label>
              <select
                id="category-parent"
                value={form.parentId}
                onChange={(e) => setForm((prev) => ({ ...prev, parentId: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="">No parent</option>
                {categories
                  .filter((c) => c.id !== editingId)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </div>
            <ImageUploader
              label="Image"
              value={form.imageUrl}
              onChange={(url) => setForm((prev) => ({ ...prev, imageUrl: url }))}
            />
            {formError && <Alert>{formError}</Alert>}
            <div className="flex gap-2">
              <Button type="submit" isLoading={isSaving}>
                {editingId ? 'Save changes' : 'Create category'}
              </Button>
              <Button type="button" variant="secondary" onClick={closeForm} disabled={isSaving}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {!isLoading && categories.length === 0 && !error && (
        <EmptyState title="No categories yet" description="Add your first category to get started." />
      )}

      {!isLoading && categories.length > 0 && (
        <Card className="divide-y divide-gray-200">
          {categories.map((category) => (
            <div key={category.id} className="flex items-center gap-4 p-4">
              <div className="h-12 w-12 shrink-0 overflow-hidden rounded-md bg-gray-100">
                {category.image_url ? (
                  <img src={category.image_url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[10px] text-gray-400">
                    No image
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-gray-900">{category.name}</p>
                <p className="text-sm text-gray-500">
                  /{category.slug}
                  {category.parent_id && (
                    <> &middot; child of {categoryNameById.get(category.parent_id) ?? 'unknown'}</>
                  )}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="secondary" size="sm" onClick={() => openEditForm(category)}>
                  Edit
                </Button>
                <Button variant="danger" size="sm" onClick={() => setDeleteTarget(category)}>
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </Card>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title={`Delete "${deleteTarget?.name}"?`}
        description={deleteError ?? 'This cannot be undone.'}
        confirmLabel="Delete"
        isDestructive
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          setDeleteTarget(null)
          setDeleteError(null)
        }}
      />
    </div>
  )
}
