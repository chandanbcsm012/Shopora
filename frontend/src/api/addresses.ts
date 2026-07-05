import { apiRequest } from './client'
import type { Address, AddressType } from './types'

export interface AddressPayload {
  full_name: string
  phone: string
  alternate_phone?: string | null
  company?: string | null
  address_line1: string
  address_line2?: string | null
  landmark?: string | null
  city: string
  district?: string | null
  state: string
  country: string
  postal_code: string
  delivery_instructions?: string | null
  address_type: AddressType
  is_default_shipping?: boolean
  is_default_billing?: boolean
  gstin?: string | null
}

export type UpdateAddressPayload = Partial<AddressPayload>

/**
 * GET /api/v1/addresses -> list[AddressOut], scoped to the current user.
 * Plain array, no pagination (per CONTRACTS.md: "address books are small").
 */
export function listAddresses(): Promise<Address[]> {
  return apiRequest<Address[]>('/addresses')
}

/** POST /api/v1/addresses -> 201 AddressOut. */
export function createAddress(data: AddressPayload): Promise<Address> {
  return apiRequest<Address>('/addresses', { method: 'POST', body: data })
}

/**
 * PATCH /api/v1/addresses/{id} -> AddressOut. 404 (RESOURCE_NOT_FOUND) if
 * missing or not owned by the caller -- the backend deliberately doesn't
 * distinguish "doesn't exist" from "exists but isn't yours".
 */
export function updateAddress(id: string, data: UpdateAddressPayload): Promise<Address> {
  return apiRequest<Address>(`/addresses/${id}`, { method: 'PATCH', body: data })
}

/** DELETE /api/v1/addresses/{id} -> 204. Same ownership check as PATCH. */
export function deleteAddress(id: string): Promise<void> {
  return apiRequest<void>(`/addresses/${id}`, { method: 'DELETE' })
}
