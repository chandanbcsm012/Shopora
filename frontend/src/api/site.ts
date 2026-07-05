import { apiRequest } from './client'

export interface ContactMessagePayload {
  name: string
  email: string
  subject: string
  message: string
}

/**
 * POST /api/v1/newsletter/subscribe {email} -> 202, no body. Public.
 * Idempotent and always the same response whether or not that email was
 * already subscribed — same no-enumeration reasoning as forgot-password.
 * Callers should show a generic success message regardless of outcome.
 */
export function subscribeToNewsletter(email: string): Promise<void> {
  return apiRequest<void>('/newsletter/subscribe', { method: 'POST', body: { email }, skipAuth: true })
}

/** POST /api/v1/contact {name, email, subject, message} -> 201, no body. Public. */
export function submitContactMessage(payload: ContactMessagePayload): Promise<void> {
  return apiRequest<void>('/contact', { method: 'POST', body: payload, skipAuth: true })
}
