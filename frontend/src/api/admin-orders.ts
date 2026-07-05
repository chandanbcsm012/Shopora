import { apiRequest } from './client'
import type { Order, OrderStatus, PaginatedResponse } from './types'

export interface ListAllOrdersParams {
  page?: number
  page_size?: number
  status?: OrderStatus
}

export interface UpdateOrderStatusPayload {
  status: OrderStatus
  note?: string
}

export interface RefundOrderPayload {
  /** Omitted = full remaining refund. */
  amount_cents?: number
}

/** GET /api/v1/admin/orders (admin/super_admin only) -> Page[OrderOut], filterable by status, newest-first by default. */
export function listAllOrders(params: ListAllOrdersParams = {}): Promise<PaginatedResponse<Order>> {
  return apiRequest<PaginatedResponse<Order>>('/admin/orders', { query: { ...params } })
}

/**
 * PATCH /api/v1/admin/orders/{id}/status (admin/super_admin only)
 * {status, note?}. No "legal transition" validation in this foundation
 * scope -- any status is accepted and always recorded as a history row.
 * ASSUMPTION: CONTRACTS.md doesn't spell out the response body; assumed to
 * mirror every other admin mutation in this app (PATCH /users/{id}/role,
 * etc.) and return the updated OrderOut, so the detail page can re-render
 * without a follow-up GET.
 */
export function updateOrderStatus(id: string, payload: UpdateOrderStatusPayload): Promise<Order> {
  return apiRequest<Order>(`/admin/orders/${id}/status`, { method: 'PATCH', body: payload })
}

/**
 * POST /api/v1/admin/orders/{id}/refund (admin/super_admin only)
 * {amount_cents?}. Updates the Payment row only -- does NOT change
 * Order.status (a refund is a payment-level fact, not an order-status one).
 * ASSUMPTION: same as updateOrderStatus -- response shape isn't specified in
 * CONTRACTS.md, assumed to return the updated OrderOut (with its refreshed
 * payment_status) for the same reason.
 */
export function refundOrder(id: string, payload: RefundOrderPayload = {}): Promise<Order> {
  return apiRequest<Order>(`/admin/orders/${id}/refund`, { method: 'POST', body: payload })
}
