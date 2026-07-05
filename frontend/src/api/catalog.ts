import { apiRequest } from './client'
import type { Brand, Category, PaginatedResponse, Product } from './types'

export type ProductSort = 'newest' | 'price_asc' | 'price_desc' | 'name_asc' | 'name_desc'

export interface ListProductsParams {
  category_id?: string
  brand_id?: string
  q?: string
  page?: number
  page_size?: number
  min_price_cents?: number
  max_price_cents?: number
  in_stock_only?: boolean
  /** Defaults to "newest" server-side (see CONTRACTS.md storefront filtering addition). */
  sort?: ProductSort
}

export interface CreateCategoryPayload {
  name: string
  slug: string
  parent_id?: string | null
  // Per CONTRACTS.md, `image_url` was added to CategoryCreate alongside
  // CategoryUpdate/CategoryOut, so the admin "add category" form can set an
  // image at creation time, not just on a follow-up edit.
  image_url?: string | null
}

export interface CreateBrandPayload {
  name: string
  slug: string
}

export interface ProductImagePayload {
  url: string
  alt_text?: string | null
  sort_order: number
}

export interface CreateProductPayload {
  name: string
  slug: string
  description?: string | null
  brand_id?: string | null
  category_id: string
  price_cents: number
  currency: string
  sku: string
  stock_quantity: number
  is_active?: boolean
  // ASSUMPTION: CONTRACTS.md defines the ProductImage table but doesn't
  // spec a dedicated image-management endpoint (no POST/PATCH/DELETE for
  // /products/{id}/images). The most consistent choice with the rest of
  // this slice (categories/brands PATCH taking the full updated shape) is
  // for ProductCreate/ProductUpdate to accept the full ordered `images`
  // array and have the backend replace it wholesale. Flagged for
  // double-checking once the backend agent's work is integrated.
  images?: ProductImagePayload[]
}

export type UpdateProductPayload = Partial<CreateProductPayload>

export type UpdateCategoryPayload = Partial<CreateCategoryPayload & { image_url: string | null }>

export type UpdateBrandPayload = Partial<CreateBrandPayload>

/**
 * GET /api/v1/categories
 * ASSUMPTION: CONTRACTS.md doesn't say categories are paginated (unlike
 * products, where pagination is explicit); we treat this as a plain array.
 */
export function listCategories(): Promise<Category[]> {
  return apiRequest<Category[]>('/categories')
}

/** POST /api/v1/categories (admin) */
export function createCategory(data: CreateCategoryPayload): Promise<Category> {
  return apiRequest<Category>('/categories', { method: 'POST', body: data })
}

/** PATCH /api/v1/categories/{id} (admin). Partial update (name, slug, parent_id, image_url). */
export function updateCategory(id: string, data: UpdateCategoryPayload): Promise<Category> {
  return apiRequest<Category>(`/categories/${id}`, { method: 'PATCH', body: data })
}

/**
 * DELETE /api/v1/categories/{id} (admin). Raises CATEGORY_IN_USE (409) if
 * the category has products or child categories.
 */
export function deleteCategory(id: string): Promise<void> {
  return apiRequest<void>(`/categories/${id}`, { method: 'DELETE' })
}

/**
 * GET /api/v1/brands
 * ASSUMPTION: same as categories, treated as a plain (non-paginated) array.
 */
export function listBrands(): Promise<Brand[]> {
  return apiRequest<Brand[]>('/brands')
}

/** POST /api/v1/brands (admin) */
export function createBrand(data: CreateBrandPayload): Promise<Brand> {
  return apiRequest<Brand>('/brands', { method: 'POST', body: data })
}

/** PATCH /api/v1/brands/{id} (admin). Partial update (name, slug). */
export function updateBrand(id: string, data: UpdateBrandPayload): Promise<Brand> {
  return apiRequest<Brand>(`/brands/${id}`, { method: 'PATCH', body: data })
}

/** DELETE /api/v1/brands/{id} (admin). Raises BRAND_IN_USE (409) if any product references it. */
export function deleteBrand(id: string): Promise<void> {
  return apiRequest<void>(`/brands/${id}`, { method: 'DELETE' })
}

/**
 * GET /api/v1/products (filters: category_id, brand_id, q, pagination).
 * Public/storefront route — the backend always excludes inactive products
 * here (never a client-controllable param), so a hidden/discontinued
 * product can't be browsed back into view.
 */
export function listProducts(params: ListProductsParams = {}): Promise<PaginatedResponse<Product>> {
  return apiRequest<PaginatedResponse<Product>>('/products', { query: { ...params } })
}

/** GET /api/v1/products/{id}. Public/storefront route — 404s for an
 * inactive product exactly like a missing one (see `getAdminProduct` for
 * the admin equivalent that can still load it for editing). */
export function getProduct(id: string): Promise<Product> {
  return apiRequest<Product>(`/products/${id}`)
}

/**
 * GET /api/v1/admin/products (admin/manager/super_admin only) — same
 * filters as `listProducts`, but includes inactive products so the admin
 * panel can find and manage (e.g. reactivate) them.
 */
export function listAdminProducts(params: ListProductsParams = {}): Promise<PaginatedResponse<Product>> {
  return apiRequest<PaginatedResponse<Product>>('/admin/products', { query: { ...params } })
}

/** GET /api/v1/admin/products/{id} (admin/manager/super_admin only) —
 * unlike `getProduct`, this loads an inactive product too (needed so the
 * product edit form can open one). */
export function getAdminProduct(id: string): Promise<Product> {
  return apiRequest<Product>(`/admin/products/${id}`)
}

/** POST /api/v1/products (admin) */
export function createProduct(data: CreateProductPayload): Promise<Product> {
  return apiRequest<Product>('/products', { method: 'POST', body: data })
}

/** PATCH /api/v1/products/{id} (admin) */
export function updateProduct(id: string, data: UpdateProductPayload): Promise<Product> {
  return apiRequest<Product>(`/products/${id}`, { method: 'PATCH', body: data })
}

/** DELETE /api/v1/products/{id} (admin) */
export function deleteProduct(id: string): Promise<void> {
  return apiRequest<void>(`/products/${id}`, { method: 'DELETE' })
}
