import { apiRequest } from './client'
import type { Invitation, PaginatedResponse, Role, User } from './types'

export interface ListUsersParams {
  page?: number
  page_size?: number
  q?: string
}

export interface InviteUserPayload {
  email: string
  full_name: string
  role: Role
  notes?: string
}

/** GET /api/v1/users (admin only). Query: page, page_size, q (email or full_name match). */
export function listUsers(params: ListUsersParams = {}): Promise<PaginatedResponse<User>> {
  return apiRequest<PaginatedResponse<User>>('/users', { query: { ...params } })
}

/**
 * PATCH /api/v1/users/{id}/role (admin only). Body {role}. Raises
 * CANNOT_MODIFY_OWN_ACCOUNT if id is the caller's own id.
 */
export function updateUserRole(id: string, role: Role): Promise<User> {
  return apiRequest<User>(`/users/${id}/role`, { method: 'PATCH', body: { role } })
}

/**
 * PATCH /api/v1/users/{id}/status (admin only). Body {is_active}. Raises
 * CANNOT_MODIFY_OWN_ACCOUNT if id is the caller's own id.
 */
export function updateUserStatus(id: string, is_active: boolean): Promise<User> {
  return apiRequest<User>(`/users/${id}/status`, { method: 'PATCH', body: { is_active } })
}

/**
 * POST /api/v1/users/invite (admin/super_admin only). Body
 * {email, full_name, role, notes?}. Enforces the role hierarchy server-side
 * (raises INSUFFICIENT_ROLE_PRIVILEGE if the caller isn't allowed to assign
 * that role). Returns the created Invitation (no raw token).
 */
export function inviteUser(payload: InviteUserPayload): Promise<Invitation> {
  return apiRequest<Invitation>('/users/invite', { method: 'POST', body: payload })
}
