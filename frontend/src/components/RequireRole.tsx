import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Spinner } from './ui'

/**
 * Stricter than RequireAdmin: used to gate a subset of routes already
 * nested under RequireAdmin (e.g. /admin/users, /admin/audit-logs) to a
 * narrower role set than the admin panel as a whole admits. RequireAdmin
 * already handles the unauthenticated case for everything under /admin, so
 * this only needs to redirect a logged-in user whose role isn't in the
 * allowed list (e.g. a `manager`, who gets into /admin for catalog access
 * but not Users/Audit Logs) back to the admin index.
 */
export default function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div role="status" className="flex justify-center py-16">
        <Spinner />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user || !roles.includes(user.role)) {
    return <Navigate to="/admin" replace />
  }
  return <>{children}</>
}
