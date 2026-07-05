import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Spinner } from './ui'

const ADMIN_PANEL_ROLES = ['admin', 'super_admin', 'manager']

/**
 * Parallel to ProtectedRoute, but additionally requires an admin-panel
 * role: unauthenticated users are sent to /login (same as ProtectedRoute,
 * so they can log back in and land back here), authenticated users outside
 * the admin/super_admin/manager hierarchy are sent to / (there's no "admin
 * login" to redirect back to for them). `manager` is admitted here (unlike
 * the old admin-only check) since managers get catalog access — routes
 * that are admin/super_admin-only specifically (Users, Audit Logs) layer
 * `RequireRole` on top of this.
 */
export default function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div role="status" className="flex justify-center py-16">
        <Spinner />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (!user || !ADMIN_PANEL_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
