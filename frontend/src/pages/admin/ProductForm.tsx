import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as catalogApi from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Brand, Category } from '../../api/types'
import { Alert, Button, Card, ImageUploader, Input, Skeleton } from '../../components/ui'
import { slugify } from '../../lib/slugify'

interface FormImage {
  url: string
  alt_text: string | null
}

interface FormState {
  name: string
  slug: string
  slugTouched: boolean
  description: string
  brandId: string
  categoryId: string
  priceDollars: string
  currency: string
  sku: string
  stockQuantity: string
  isActive: boolean
  images: FormImage[]
}

const EMPTY_FORM: FormState = {
  name: '',
  slug: '',
  slugTouched: false,
  description: '',
  brandId: '',
  categoryId: '',
  priceDollars: '',
  currency: 'USD',
  sku: '',
  stockQuantity: '0',
  isActive: true,
  images: [],
}

/** Shared by /admin/products/new and /admin/products/:id/edit. */
export default function ProductForm() {
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)
  const navigate = useNavigate()

  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [isLoading, setIsLoading] = useState(isEdit)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    catalogApi
      .listCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
    catalogApi
      .listBrands()
      .then(setBrands)
      .catch(() => setBrands([]))
  }, [])

  useEffect(() => {
    if (!id) return
    setIsLoading(true)
    catalogApi
      .getAdminProduct(id)
      .then((product) => {
        const sortedImages = [...(product.images ?? [])].sort((a, b) => a.sort_order - b.sort_order)
        setForm({
          name: product.name,
          slug: product.slug,
          slugTouched: true,
          description: product.description ?? '',
          brandId: product.brand_id ?? '',
          categoryId: product.category_id,
          priceDollars: (product.price_cents / 100).toFixed(2),
          currency: product.currency,
          sku: product.sku,
          stockQuantity: String(product.stock_quantity),
          isActive: product.is_active,
          images: sortedImages.map((img) => ({ url: img.url, alt_text: img.alt_text })),
        })
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : 'Failed to load product'))
      .finally(() => setIsLoading(false))
  }, [id])

  function moveImage(index: number, direction: -1 | 1) {
    setForm((prev) => {
      const next = [...prev.images]
      const targetIndex = index + direction
      if (targetIndex < 0 || targetIndex >= next.length) return prev
      ;[next[index], next[targetIndex]] = [next[targetIndex], next[index]]
      return { ...prev, images: next }
    })
  }

  function removeImage(index: number) {
    setForm((prev) => ({ ...prev, images: prev.images.filter((_, i) => i !== index) }))
  }

  function addImage(url: string | null) {
    if (!url) return
    setForm((prev) => ({ ...prev, images: [...prev.images, { url, alt_text: null }] }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaveError(null)

    const priceCents = Math.round(Number(form.priceDollars) * 100)
    if (!Number.isFinite(priceCents) || priceCents < 0) {
      setSaveError('Enter a valid price.')
      return
    }

    const payload = {
      name: form.name,
      slug: form.slug,
      description: form.description || null,
      brand_id: form.brandId || null,
      category_id: form.categoryId,
      price_cents: priceCents,
      currency: form.currency,
      sku: form.sku,
      stock_quantity: Number(form.stockQuantity) || 0,
      is_active: form.isActive,
      images: form.images.map((img, index) => ({ url: img.url, alt_text: img.alt_text, sort_order: index })),
    }

    setIsSaving(true)
    try {
      if (id) {
        await catalogApi.updateProduct(id, payload)
      } else {
        await catalogApi.createProduct(payload)
      }
      navigate('/admin/products')
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Failed to save product')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl">
        <Skeleton className="mb-4 h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (loadError) return <Alert>{loadError}</Alert>

  return (
    <div className="max-w-2xl">
      <h2 className="mb-6 text-lg font-medium text-gray-900">{isEdit ? 'Edit product' : 'New product'}</h2>
      <Card className="p-6">
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
          <div className="flex flex-col gap-1.5">
            <label htmlFor="product-description" className="text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="product-description"
              rows={4}
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product-category" className="text-sm font-medium text-gray-700">
                Category
              </label>
              <select
                id="product-category"
                required
                value={form.categoryId}
                onChange={(e) => setForm((prev) => ({ ...prev, categoryId: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="" disabled>
                  Select a category
                </option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product-brand" className="text-sm font-medium text-gray-700">
                Brand
              </label>
              <select
                id="product-brand"
                value={form.brandId}
                onChange={(e) => setForm((prev) => ({ ...prev, brandId: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="">No brand</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product-price" className="text-sm font-medium text-gray-700">
                Price
              </label>
              <input
                id="product-price"
                type="number"
                step="0.01"
                min="0"
                required
                value={form.priceDollars}
                onChange={(e) => setForm((prev) => ({ ...prev, priceDollars: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product-currency" className="text-sm font-medium text-gray-700">
                Currency
              </label>
              <select
                id="product-currency"
                value={form.currency}
                onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="USD">USD</option>
                <option value="INR">INR</option>
              </select>
            </div>
            <Input
              label="SKU"
              required
              value={form.sku}
              onChange={(e) => setForm((prev) => ({ ...prev, sku: e.target.value }))}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product-stock" className="text-sm font-medium text-gray-700">
                Stock quantity
              </label>
              <input
                id="product-stock"
                type="number"
                min="0"
                step="1"
                required
                value={form.stockQuantity}
                onChange={(e) => setForm((prev) => ({ ...prev, stockQuantity: e.target.value }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
            <input
              type="checkbox"
              checked={form.isActive}
              onChange={(e) => setForm((prev) => ({ ...prev, isActive: e.target.checked }))}
              className="h-4 w-4 rounded border-gray-300"
            />
            Active (visible in the storefront)
          </label>

          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium text-gray-700">Images</p>
            {form.images.length > 0 && (
              <ul className="flex flex-col gap-2">
                {form.images.map((image, index) => (
                  <li key={`${image.url}-${index}`} className="flex items-center gap-3 rounded-md border border-gray-200 p-2">
                    <img src={image.url} alt="" className="h-12 w-12 rounded-md object-cover" />
                    <span className="flex-1 truncate text-xs text-gray-500">{image.url}</span>
                    <button
                      type="button"
                      onClick={() => moveImage(index, -1)}
                      disabled={index === 0}
                      aria-label="Move image up"
                      className="rounded-md border border-gray-300 px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      &uarr;
                    </button>
                    <button
                      type="button"
                      onClick={() => moveImage(index, 1)}
                      disabled={index === form.images.length - 1}
                      aria-label="Move image down"
                      className="rounded-md border border-gray-300 px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      &darr;
                    </button>
                    <button
                      type="button"
                      onClick={() => removeImage(index)}
                      className="rounded-md border border-gray-300 px-2 py-1 text-xs text-danger-600 hover:bg-danger-50"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <ImageUploader label="Add an image" value={null} onChange={addImage} />
          </div>

          {saveError && <Alert>{saveError}</Alert>}

          <div className="flex gap-2">
            <Button type="submit" isLoading={isSaving}>
              {isEdit ? 'Save changes' : 'Create product'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate('/admin/products')} disabled={isSaving}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
