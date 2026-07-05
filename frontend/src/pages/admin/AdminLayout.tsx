import { NavLink, Outlet } from 'react-router-dom'
import type { Role } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import { cn } from '../../lib/cn'

const tabClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium',
    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
  )

interface Tab {
  to: string
  label: string
  /** Omitted = visible to everyone RequireAdmin already admits. */
  roles?: Role[]
}

const TABS: Tab[] = [
  { to: '/admin/categories', label: 'Categories' },
  { to: '/admin/brands', label: 'Brands' },
  { to: '/admin/products', label: 'Products' },
  { to: '/admin/orders', label: 'Orders', roles: ['admin', 'super_admin'] },
  { to: '/admin/users', label: 'Users', roles: ['admin', 'super_admin'] },
  { to: '/admin/audit-logs', label: 'Audit Logs', roles: ['admin', 'super_admin'] },
]

/**
 * Not a route itself — a layout wrapping all /admin/* routes (except the
 * standalone /admin/setup) with a shared tab bar, same active-link styling
 * approach as Nav.tsx's linkClassName. Tabs are filtered per-role: managers
 * get into /admin (RequireAdmin) for catalog access but shouldn't see the
 * Users/Audit Logs tabs — the routes themselves are also guarded by
 * RequireRole in App.tsx, so hiding the tab is a UX nicety, not the only
 * protection against a manager navigating there directly by URL.
 */
export default function AdminLayout() {
  const { user } = useAuth()
  const tabs = TABS.filter((tab) => !tab.roles || (user && tab.roles.includes(user.role)))

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight text-gray-900">Admin</h1>
      <nav aria-label="Admin sections" className="mb-6 flex items-center gap-1 border-b border-gray-200 pb-2">
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={tabClassName}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}
