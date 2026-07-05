import { ApiError, apiRequest, buildUrl, getAuthToken } from './client'
import type { Cart, ErrorEnvelope, Order, OrderStatusHistory, PaginatedResponse, PaymentMethod } from './types'

export interface AddCartItemPayload {
  product_id: string
  quantity: number
}

export interface UpdateCartItemPayload {
  quantity: number
}

export interface ListOrdersParams {
  page?: number
  page_size?: number
}

export interface CheckoutPayload {
  shipping_address_id: string
  billing_address_id: string
  payment_method: PaymentMethod
  /** Ignored for `cod`; defaults to "succeed" server-side if omitted for `test_card`. */
  test_card_outcome?: 'succeed' | 'decline'
}

/** GET /api/v1/cart -> current user's cart (creates an empty one if absent) */
export function getCart(): Promise<Cart> {
  return apiRequest<Cart>('/cart')
}

/**
 * POST /api/v1/cart/items {product_id, quantity}
 * ASSUMPTION: CONTRACTS.md doesn't state the response body for cart
 * mutations; we assume the endpoint returns the updated Cart (with items),
 * which is what the UI needs to re-render without an extra GET /cart.
 */
export function addCartItem(data: AddCartItemPayload): Promise<Cart> {
  return apiRequest<Cart>('/cart/items', { method: 'POST', body: data })
}

/** PATCH /api/v1/cart/items/{item_id} {quantity} -- see addCartItem assumption on response shape */
export function updateCartItem(itemId: string, data: UpdateCartItemPayload): Promise<Cart> {
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: 'PATCH', body: data })
}

/** DELETE /api/v1/cart/items/{item_id} -- see addCartItem assumption on response shape */
export function removeCartItem(itemId: string): Promise<Cart> {
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: 'DELETE' })
}

/**
 * POST /api/v1/orders/checkout {shipping_address_id, billing_address_id,
 * payment_method, test_card_outcome?} -> creates Order from current cart,
 * empties cart. Per CONTRACTS.md the cart is emptied as part of Order
 * creation regardless of payment outcome -- even a declined test-card
 * checkout leaves a (cancelled) Order behind and an empty cart, while this
 * call still throws `ApiError` (status 402, code PAYMENT_FAILED) rather than
 * resolving. Callers should treat a 402 here as "the cart is already gone,
 * not just this request failed".
 */
export function checkout(payload: CheckoutPayload): Promise<Order> {
  return apiRequest<Order>('/orders/checkout', { method: 'POST', body: payload })
}

/** GET /api/v1/orders -> current user's orders (paginated) */
export function listOrders(params: ListOrdersParams = {}): Promise<PaginatedResponse<Order>> {
  return apiRequest<PaginatedResponse<Order>>('/orders', { query: { ...params } })
}

/** GET /api/v1/orders/{id} */
export function getOrder(id: string): Promise<Order> {
  return apiRequest<Order>(`/orders/${id}`)
}

/** GET /api/v1/orders/{id}/timeline -> list[OrderStatusHistoryOut], oldest first. Owner or admin/super_admin. */
export function getOrderTimeline(orderId: string): Promise<OrderStatusHistory[]> {
  return apiRequest<OrderStatusHistory[]>(`/orders/${orderId}/timeline`)
}

/**
 * GET /api/v1/orders/{id}/invoice -> raw `application/pdf` bytes, not JSON,
 * so this bypasses `apiRequest<T>`'s JSON-only assumption entirely: it does
 * its own `fetch` with the same Bearer token apiRequest attaches, reads the
 * response as a `Blob`, and triggers a browser download via a temporary
 * object URL + a hidden `<a download>` click (then revokes the URL). Throws
 * `ApiError` on a non-2xx JSON error envelope (e.g. INVOICE_NOT_AVAILABLE,
 * 404, if no Invoice exists yet for this order).
 */
export async function downloadInvoice(orderId: string, filename: string): Promise<void> {
  const token = getAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(buildUrl(`/orders/${orderId}/invoice`), { headers })

  if (!response.ok) {
    const text = await response.text()
    let payload: unknown = null
    try {
      payload = text ? JSON.parse(text) : null
    } catch {
      payload = null
    }
    const envelope = payload as ErrorEnvelope | null
    if (envelope?.error) {
      throw new ApiError(response.status, envelope.error.code, envelope.error.message, envelope.error.details)
    }
    throw new ApiError(response.status, 'INTERNAL_ERROR', response.statusText || 'Failed to download invoice')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
