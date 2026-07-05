import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import * as catalogApi from '../api/catalog'
import type { ProductSort } from '../api/catalog'
import type { Category, Product } from '../api/types'
import { ProductCard, ProductCardSkeleton } from '../components/ProductCard'
import { Alert, Button, EmptyState } from '../components/ui'
import { usePagination } from '../hooks/usePagination'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 400

const SORT_OPTIONS: { value: ProductSort; label: string }[] = [
  { value: 'newest', label: 'Newest' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'name_asc', label: 'Name: A-Z' },
  { value: 'name_desc', label: 'Name: Z-A' },
]

export default function ProductList() {
  // Read-only on mount: lets the homepage's category/brand showcase link
  // straight into a pre-filtered listing (`/products?category_id=...`)
  // without a full two-way URL sync, which this app's existing pages don't
  // do anywhere else either.
  const [searchParams] = useSearchParams()

  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const { page, setPage, totalPages, goToPrevious, goToNext } = usePagination(total, PAGE_SIZE)

  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState(() => searchParams.get('category_id') ?? '')
  const [brandId] = useState(() => searchParams.get('brand_id') ?? '')
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [inStockOnly, setInStockOnly] = useState(false)
  const [sort, setSort] = useState<ProductSort>('newest')

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    catalogApi
      .listCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  // Debounced search: fires 400ms after the user stops typing, rather than
  // requiring an explicit submit — fewer clicks for the common case, and
  // avoids firing a request per keystroke.
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

    // ProductForm.tsx's price field does the same dollars->cents conversion
    // (Math.round(dollars * 100)) before sending to the API.
    const minPriceCents = minPrice.trim() ? Math.round(Number(minPrice) * 100) : undefined
    const maxPriceCents = maxPrice.trim() ? Math.round(Number(maxPrice) * 100) : undefined

    catalogApi
      .listProducts({
        page,
        page_size: PAGE_SIZE,
        category_id: categoryId || undefined,
        brand_id: brandId || undefined,
        q: query || undefined,
        min_price_cents: minPriceCents !== undefined && Number.isFinite(minPriceCents) ? minPriceCents : undefined,
        max_price_cents: maxPriceCents !== undefined && Number.isFinite(maxPriceCents) ? maxPriceCents : undefined,
        in_stock_only: inStockOnly || undefined,
        sort,
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
  }, [page, categoryId, brandId, query, minPrice, maxPrice, inStockOnly, sort])

  const hasFilters =
    categoryId !== '' || brandId !== '' || query !== '' || minPrice !== '' || maxPrice !== '' || inStockOnly

  const activeCategory = categories.find((c) => c.id === categoryId)

  function clearFilters() {
    setSearchInput('')
    setQuery('')
    setCategoryId('')
    setMinPrice('')
    setMaxPrice('')
    setInStockOnly(false)
    setSort('newest')
    setPage(1)
  }

  return (
    <div>
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-gray-500">
        <Link to="/" className="hover:text-gray-900">
          Home
        </Link>
        <span className="mx-1.5">/</span>
        {activeCategory ? (
          <>
            <Link to="/products" className="hover:text-gray-900">
              Products
            </Link>
            <span className="mx-1.5">/</span>
            <span className="text-gray-900">{activeCategory.name}</span>
          </>
        ) : (
          <span className="text-gray-900">Products</span>
        )}
      </nav>

      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Products</h1>

      <div className="mb-6 flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="product-search" className="text-sm font-medium text-gray-700">
              Search
            </label>
            <input
              id="product-search"
              type="search"
              placeholder="Search products…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="h-10 w-full min-w-0 rounded-md border border-gray-300 px-3 text-sm sm:w-64"
            />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="category-filter" className="text-sm font-medium text-gray-700">
              Category
            </label>
            <select
              id="category-filter"
              value={categoryId}
              onChange={(e) => {
                setPage(1)
                setCategoryId(e.target.value)
              }}
              className="h-10 w-full min-w-0 rounded-md border border-gray-300 px-3 text-sm sm:w-auto"
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="product-sort" className="text-sm font-medium text-gray-700">
              Sort by
            </label>
            <select
              id="product-sort"
              value={sort}
              onChange={(e) => {
                setPage(1)
                setSort(e.target.value as ProductSort)
              }}
              className="h-10 w-full min-w-0 rounded-md border border-gray-300 px-3 text-sm sm:w-auto"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="min-price" className="text-sm font-medium text-gray-700">
              Min price ($)
            </label>
            <input
              id="min-price"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              placeholder="0.00"
              value={minPrice}
              onChange={(e) => {
                setPage(1)
                setMinPrice(e.target.value)
              }}
              className="h-10 w-28 rounded-md border border-gray-300 px-3 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="max-price" className="text-sm font-medium text-gray-700">
              Max price ($)
            </label>
            <input
              id="max-price"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              placeholder="No limit"
              value={maxPrice}
              onChange={(e) => {
                setPage(1)
                setMaxPrice(e.target.value)
              }}
              className="h-10 w-28 rounded-md border border-gray-300 px-3 text-sm"
            />
          </div>
          <label className="flex h-10 items-center gap-2 text-sm font-medium text-gray-700">
            <input
              id="in-stock-only"
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => {
                setPage(1)
                setInStockOnly(e.target.checked)
              }}
              className="h-4 w-4 rounded border-gray-300"
            />
            In stock only
          </label>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" aria-hidden="true">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!isLoading && products.length === 0 && !error && (
        <EmptyState
          title="No products found"
          description={hasFilters ? 'Try different filters or search term.' : 'Check back soon.'}
          action={
            hasFilters && (
              <Button variant="secondary" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            )
          }
        />
      )}

      {!isLoading && products.length > 0 && (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {products.map((product) => (
            <li key={product.id}>
              <ProductCard product={product} />
            </li>
          ))}
        </ul>
      )}

      {!isLoading && products.length > 0 && totalPages > 1 && (
        <nav aria-label="Products pagination" className="mt-6 flex items-center justify-center gap-3">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={goToPrevious}>
            Previous
          </Button>
          <span className="text-sm text-gray-600" aria-live="polite">
            Page {page} of {totalPages}
          </span>
          <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={goToNext}>
            Next
          </Button>
        </nav>
      )}
    </div>
  )
}
