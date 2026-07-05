import { apiRequest } from './client'
import type { AuthTokens, InvitationPreview, User } from './types'

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface BootstrapPayload {
  email: string
  password: string
  full_name: string
}

/** POST /api/v1/auth/register -> 201 User (no password) */
export function register(data: RegisterPayload): Promise<User> {
  return apiRequest<User>('/auth/register', { method: 'POST', body: data, skipAuth: true })
}

/** POST /api/v1/auth/login -> {access_token, refresh_token, token_type} */
export function login(data: LoginPayload): Promise<AuthTokens> {
  return apiRequest<AuthTokens>('/auth/login', { method: 'POST', body: data, skipAuth: true })
}

/**
 * POST /api/v1/auth/refresh -> same shape, rotates refresh token.
 * ASSUMPTION: CONTRACTS.md doesn't state how the refresh token is
 * transmitted; we send it as `{refresh_token}` in the JSON body.
 */
export function refresh(refreshToken: string): Promise<AuthTokens> {
  return apiRequest<AuthTokens>('/auth/refresh', {
    method: 'POST',
    body: { refresh_token: refreshToken },
    skipAuth: true,
  })
}

/**
 * POST /api/v1/auth/logout -> 204, revokes refresh token.
 * ASSUMPTION: same as refresh, we pass `{refresh_token}` in the body.
 */
export function logout(refreshToken: string): Promise<void> {
  return apiRequest<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } })
}

/** GET /api/v1/auth/me -> current User */
export function me(): Promise<User> {
  return apiRequest<User>('/auth/me')
}

/**
 * GET /api/v1/auth/bootstrap-status -> {admin_exists} (public, no auth).
 * Used by the setup wizard to decide whether to show the create-admin form.
 */
export function getBootstrapStatus(): Promise<{ admin_exists: boolean }> {
  return apiRequest<{ admin_exists: boolean }>('/auth/bootstrap-status', { skipAuth: true })
}

/**
 * POST /api/v1/auth/bootstrap -> TokenPair (201). Public, but self-limiting:
 * raises SETUP_ALREADY_COMPLETED (409) if an admin already exists. Creates
 * a role="admin" user and logs it in immediately, same as register->login.
 */
export function bootstrap(data: BootstrapPayload): Promise<AuthTokens> {
  return apiRequest<AuthTokens>('/auth/bootstrap', { method: 'POST', body: data, skipAuth: true })
}

export interface AcceptInvitationPayload {
  token: string
  password: string
}

export interface ResetPasswordPayload {
  token: string
  new_password: string
}

/**
 * GET /api/v1/auth/invitations/{token} -> InvitationPreview (public).
 * Raises INVITATION_INVALID / INVITATION_EXPIRED / INVITATION_ALREADY_ACCEPTED
 * as an ApiError when the token doesn't resolve to a pending invitation.
 */
export function getInvitationPreview(token: string): Promise<InvitationPreview> {
  return apiRequest<InvitationPreview>(`/auth/invitations/${encodeURIComponent(token)}`, { skipAuth: true })
}

/**
 * POST /api/v1/auth/accept-invitation -> TokenPair (public). Behaves like
 * register/bootstrap: auto-login on success, so callers should feed the
 * result into AuthContext's applyTokens (see acceptInvitation there).
 */
export function acceptInvitation(data: AcceptInvitationPayload): Promise<AuthTokens> {
  return apiRequest<AuthTokens>('/auth/accept-invitation', { method: 'POST', body: data, skipAuth: true })
}

/**
 * POST /api/v1/auth/forgot-password -> 202, no body (public). Always
 * "succeeds" regardless of whether the email is registered, per
 * CONTRACTS.md's no-user-enumeration requirement — callers should show the
 * same generic message whether this resolves or rejects.
 */
export function forgotPassword(email: string): Promise<void> {
  return apiRequest<void>('/auth/forgot-password', { method: 'POST', body: { email }, skipAuth: true })
}

/**
 * POST /api/v1/auth/reset-password -> 204 (public). Does NOT auto-login
 * (unlike accept-invitation) — the backend revokes all of the user's
 * existing refresh tokens, so the intended flow is a fresh login after.
 */
export function resetPassword(data: ResetPasswordPayload): Promise<void> {
  return apiRequest<void>('/auth/reset-password', { method: 'POST', body: data, skipAuth: true })
}
