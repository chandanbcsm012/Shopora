// Shared DTO types mirroring docs/CONTRACTS.md "Core data contracts" section.
// Money is always integer minor units (`*_cents`) + an ISO-4217 `currency`.

/** See the NOTE on `Cart` below: the cart response carries no currency. */
export const USD_FALLBACK = 'USD'

export interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type Role = 'customer' | 'manager' | 'admin' | 'super_admin'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Returned by POST /users/invite (without the raw token). */
export interface Invitation {
  id: string
  email: string
  full_name: string
  role: Role
  expires_at: string
  accepted_at: string | null
}

/** Returned by the public GET /auth/invitations/{token} preview endpoint. */
export interface InvitationPreview {
  email: string
  full_name: string
  role: Role
  expires_at: string
}

export interface AuditLog {
  id: string
  actor_user_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface Category {
  id: string
  name: string
  slug: string
  parent_id: string | null
  image_url: string | null
  created_at: string
  updated_at: string
}

export interface Brand {
  id: string
  name: string
  slug: string
  created_at: string
  updated_at: string
}

export interface ProductImage {
  id: string
  product_id: string
  url: string
  alt_text: string | null
  sort_order: number
}

export interface Product {
  id: string
  name: string
  slug: string
  description: string | null
  brand_id: string | null
  category_id: string
  price_cents: number
  currency: string
  sku: string
  stock_quantity: number
  is_active: boolean
  created_at: string
  updated_at: string
  images?: ProductImage[]
}

export interface CartItem {
  id: string
  product_id: string
  quantity: number
  unit_price_cents: number
  line_total_cents: number
}

// NOTE: the real CartOut has no currency field at all (verified against
// app/modules/orders/schemas.py) — every product is USD in this slice, so
// pages hardcode the USD_FALLBACK currency below rather than reading one
// off the cart. Revisit if/when multi-currency support lands.
export interface Cart {
  id: string
  items: CartItem[]
  subtotal_cents: number
}

export type OrderStatus = 'pending' | 'paid' | 'shipped' | 'delivered' | 'cancelled'

export type AddressType = 'home' | 'office' | 'warehouse' | 'other'

/** Owned by the `addresses` module; a user's self-service address book entry. */
export interface Address {
  id: string
  full_name: string
  phone: string
  alternate_phone: string | null
  company: string | null
  address_line1: string
  address_line2: string | null
  landmark: string | null
  city: string
  district: string | null
  state: string
  country: string
  postal_code: string
  delivery_instructions: string | null
  address_type: AddressType
  is_default_shipping: boolean
  is_default_billing: boolean
  /** Buyer GSTIN for B2B invoices (India-specific, optional). Format-validated
   * server-side, not government-verified. */
  gstin: string | null
  created_at: string
  updated_at: string
}

/** `Payment.method` values (see the `payments` module's adapter registry). No
 * real-card fields exist anywhere in this method — `test_card` is a demo
 * path that only ever asks for a simulated succeed/decline outcome. */
export type PaymentMethod = 'cod' | 'test_card'

export interface OrderItem {
  id: string
  product_id: string
  product_name_snapshot: string
  quantity: number
  unit_price_cents: number
  line_total_cents: number
}

/** Append-only audit trail of `Order.status` transitions (checkout, payment
 * result, or an admin status change) — one row per write, oldest first from
 * GET /orders/{id}/timeline. */
export interface OrderStatusHistory {
  id: string
  order_id: string
  from_status: OrderStatus | null
  to_status: OrderStatus
  note: string | null
  created_at: string
}

export interface Order {
  id: string
  status: OrderStatus
  total_cents: number
  currency: string
  items: OrderItem[]
  created_at: string
  // Nullable: existing orders predate these columns, and both are only
  // embedded once addresses are attached at checkout time (see CONTRACTS.md
  // "orders module extensions").
  shipping_address: Address | null
  billing_address: Address | null
  // `Payment.status` values: "pending"|"authorized"|"captured"|"failed"|
  // "cancelled"|"refunded"|"partially_refunded"|"expired". Left as `string`
  // (not a union) since it's a free-form field on the Payment model, not an
  // enum the frontend enforces.
  payment_status: string | null
  // Only present once an Invoice row exists (payment succeeded at least
  // once) — `f"INV-{sequence_number:06d}"`, computed server-side.
  invoice_number: string | null
  // GST tax breakdown (see CONTRACTS.md "INR Currency & GST") — all null
  // unless the order is INR and GST was enabled/applicable at checkout.
  // `total_cents` above keeps its original pre-tax meaning for backward
  // compatibility; `grand_total_cents` (when present) is the actual amount
  // charged/displayed as the order's bottom line.
  taxable_amount_cents: number | null
  cgst_cents: number | null
  sgst_cents: number | null
  igst_cents: number | null
  tax_total_cents: number | null
  grand_total_cents: number | null
}

/** `order.grand_total_cents ?? order.total_cents` — use this everywhere a
 * "Total" is displayed, per CONTRACTS.md, so GST-inclusive orders show the
 * actual amount charged rather than the pre-tax subtotal. */
export function orderDisplayTotalCents(order: Order): number {
  return order.grand_total_cents ?? order.total_cents
}
