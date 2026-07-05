import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import * as catalogApi from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Brand, Category, Product } from '../../api/types'
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Skeleton } from '../../components/ui'
import { usePagination } from '../../hooks/usePagination'
import { formatMoney } from '../../lib/format'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 400

export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const { page, setPage, totalPages, goToPrevious, goToNext } = usePagination(total, PAGE_SIZE)

  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [brandId, setBrandId] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')

  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const categoryNameById = useMemo(() => new Map(categories.map((c) => [c.id, c.name])), [categories])
  const brandNameById = useMemo(() => new Map(brands.map((b) => [b.id, b.name])), [brands])

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
    const handle = setTimeout(() => {
      setPage(1)
      setQuery(searchInput.trim())
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setPage identity is stable
  }, [searchInput])

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)
    catalogApi
      .listAdminProducts({
        page,
        page_size: PAGE_SIZE,
        category_id: categoryId || undefined,
        brand_id: brandId || undefined,
        q: query || undefined,
      })
      .then((result) => {
        if (cancelled) return
        setProducts(result.items)
        setTotal(result.total)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load products')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, categoryId, brandId, query])

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await catalogApi.deleteProduct(deleteTarget.id)
      setProducts((prev) => prev.filter((p) => p.id !== deleteTarget.id))
      setTotal((t) => Math.max(0, t - 1))
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Failed to delete product')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="admin-product-search" className="text-sm font-medium text-gray-700">
              Search
            </label>
            <input
              id="admin-product-search"
              type="search"
              placeholder="Search products…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="h-10 w-56 rounded-md border border-gray-300 px-3 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="admin-category-filter" className="text-sm font-medium text-gray-700">
              Category
            </label>
            <select
              id="admin-category-filter"
              value={categoryId}
              onChange={(e) => {
                setPage(1)
                setCategoryId(e.target.value)
              }}
              className="h-10 rounded-md border border-gray-300 px-3 text-sm"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="admin-brand-filter" className="text-sm font-medium text-gray-700">
              Brand
            </label>
            <select
              id="admin-brand-filter"
              value={brandId}
              onChange={(e) => {
                setPage(1)
                setBrandId(e.target.value)
              }}
              className="h-10 rounded-md border border-gray-300 px-3 text-sm"
            >
              <option value="">All brands</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Link to="/admin/products/new">
          <Button size="sm">Add product</Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {!isLoading && products.length === 0 && !error && (
        <EmptyState title="No products found" description="Try a different search or filter." />
      )}

      {!isLoading && products.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Brand</th>
                <th className="px-4 py-3 font-medium">Price</th>
                <th className="px-4 py-3 font-medium">Stock</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {products.map((product) => {
                const image = product.images?.[0]
                return (
                  <tr key={product.id}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-md bg-gray-100">
                          {image ? (
                            <img src={image.url} alt="" className="h-full w-full object-cover" />
                          ) : null}
                        </div>
                        <span className="font-medium text-gray-900">{product.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {categoryNameById.get(product.category_id) ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {product.brand_id ? (brandNameById.get(product.brand_id) ?? '—') : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-900">{formatMoney(product.price_cents, product.currency)}</td>
                    <td className="px-4 py-3 text-gray-700">{product.stock_quantity}</td>
                    <td className="px-4 py-3">
                      <Badge tone={product.is_active ? 'success' : 'neutral'}>
                        {product.is_active ? 'active' : 'inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <Link to={`/admin/products/${product.id}/edit`}>
                          <Button variant="secondary" size="sm">
                            Edit
                          </Button>
                        </Link>
                        <Button variant="danger" size="sm" onClick={() => setDeleteTarget(product)}>
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}

      {!isLoading && products.length > 0 && totalPages > 1 && (
        <nav aria-label="Products pagination" className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={page <= 1}
            onClick={goToPrevious}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600" aria-live="polite">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={goToNext}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </nav>
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
