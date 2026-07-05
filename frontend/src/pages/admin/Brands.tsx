import { useEffect, useState, type FormEvent } from 'react'
import * as catalogApi from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Brand } from '../../api/types'
import { Alert, Button, Card, ConfirmDialog, EmptyState, Input, Skeleton } from '../../components/ui'
import { slugify } from '../../lib/slugify'

interface FormState {
  name: string
  slug: string
  slugTouched: boolean
}

const EMPTY_FORM: FormState = { name: '', slug: '', slugTouched: false }

/** Same pattern as Categories.tsx, simplified: no image, no parent. */
export default function Brands() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<Brand | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    setIsLoading(true)
    setError(null)
    catalogApi
      .listBrands()
      .then(setBrands)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load brands'))
      .finally(() => setIsLoading(false))
  }, [])

  function openCreateForm() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setIsFormOpen(true)
  }

  function openEditForm(brand: Brand) {
    setEditingId(brand.id)
    setForm({ name: brand.name, slug: brand.slug, slugTouched: true })
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
    const payload = { name: form.name, slug: form.slug }
    try {
      if (editingId) {
        const updated = await catalogApi.updateBrand(editingId, payload)
        setBrands((prev) => prev.map((b) => (b.id === updated.id ? updated : b)))
      } else {
        const created = await catalogApi.createBrand(payload)
        setBrands((prev) => [...prev, created])
      }
      closeForm()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to save brand')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await catalogApi.deleteBrand(deleteTarget.id)
      setBrands((prev) => prev.filter((b) => b.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Failed to delete brand')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-medium text-gray-900">Brands</h2>
        {!isFormOpen && <Button size="sm" onClick={openCreateForm}>Add brand</Button>}
      </div>

      {isFormOpen && (
        <Card className="mb-6 p-4">
          <h3 className="mb-4 text-sm font-semibold text-gray-900">{editingId ? 'Edit brand' : 'New brand'}</h3>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Name"
              required
              value={form.name}
              onChange={(e) => {
                const name = e.target.value
                setForm((prev) => ({ ...prev, name, slug: prev.slugTouched ? prev.slug : slugify(name) }))
              }}
            />
            <Input
              label="Slug"
              required
              value={form.slug}
              onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value, slugTouched: true }))}
              hint="Auto-suggested from the name; edit freely."
            />
            {formError && <Alert>{formError}</Alert>}
            <div className="flex gap-2">
              <Button type="submit" isLoading={isSaving}>
                {editingId ? 'Save changes' : 'Create brand'}
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
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {!isLoading && brands.length === 0 && !error && (
        <EmptyState title="No brands yet" description="Add your first brand to get started." />
      )}

      {!isLoading && brands.length > 0 && (
        <Card className="divide-y divide-gray-200">
          {brands.map((brand) => (
            <div key={brand.id} className="flex items-center gap-4 p-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-gray-900">{brand.name}</p>
                <p className="text-sm text-gray-500">/{brand.slug}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="secondary" size="sm" onClick={() => openEditForm(brand)}>
                  Edit
                </Button>
                <Button variant="danger" size="sm" onClick={() => setDeleteTarget(brand)}>
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
