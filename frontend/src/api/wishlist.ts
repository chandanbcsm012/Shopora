import { apiRequest } from './client'

/**
 * Deliberately NOT embedding product details (see CONTRACTS.md "New
 * wishlist module") — the frontend enriches by calling
 * `catalogApi.getProduct(product_id)` per item, exactly like CartContext
 * already does for cart line items (see WishlistContext).
 */
export interface WishlistItem {
  id: string
  product_id: string
  created_at: string
}

/** GET /api/v1/wishlist -> current user's wishlist items. Plain array, no
 * pagination (wishlists are small, same reasoning as addresses/categories). */
export function listWishlist(): Promise<WishlistItem[]> {
  return apiRequest<WishlistItem[]>('/wishlist')
}

/**
 * POST /api/v1/wishlist {product_id} -> 201 WishlistItem. Idempotent per
 * CONTRACTS.md: adding an already-wishlisted product returns the existing
 * row rather than a conflict error.
 */
export function addToWishlist(productId: string): Promise<WishlistItem> {
  return apiRequest<WishlistItem>('/wishlist', { method: 'POST', body: { product_id: productId } })
}

/** DELETE /api/v1/wishlist/{product_id} -> 204, idempotent (204 whether or
 * not it was actually wishlisted). */
export function removeFromWishlist(productId: string): Promise<void> {
  return apiRequest<void>(`/wishlist/${productId}`, { method: 'DELETE' })
}
