import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { cn } from '../lib/cn'
import { Button } from './ui'

const linkClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium',
    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
  )

// Same set RequireAdmin admits: admin/super_admin get the full panel,
// manager gets in for catalog access only (its own tabs are hidden by
// AdminLayout and its routes gated by RequireRole).
const ADMIN_PANEL_ROLES = ['admin', 'super_admin', 'manager']

/**
 * Previously a single `flex flex-wrap` row holding brand + 5-6 links +
 * the user's email + logout: on a phone-width viewport this wraps into a
 * ragged multi-line stack with no clear grouping, and NavLink didn't
 * indicate the current page at all. Splitting into a persistent bar
 * (brand + cart, always visible — cart is the one thing a shopper needs
 * at every screen size) plus a disclosure menu for the rest fixes both:
 * fewer items competing for space on mobile, and `aria-current`/active
 * styling now shows where you are.
 */
export default function Nav() {
  const { user, isAuthenticated, logout } = useAuth()
  const { itemCount } = useCart()
  const navigate = useNavigate()
  const location = useLocation()
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  useEffect(() => {
    setIsMenuOpen(false)
  }, [location.pathname])

  async function handleLogout() {
    await logout()
    setIsMenuOpen(false)
    navigate('/')
  }

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link to="/" className="text-lg font-semibold tracking-tight text-gray-900">
          Shopora
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 sm:flex">
          <NavLink to="/" end className={linkClassName}>
            Home
          </NavLink>
          <NavLink to="/products" className={linkClassName}>
            Products
          </NavLink>
          {isAuthenticated && (
            <NavLink to="/wishlist" className={linkClassName}>
              Wishlist
            </NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/orders" className={linkClassName}>
              Orders
            </NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/addresses" className={linkClassName}>
              Addresses
            </NavLink>
          )}
          {user && ADMIN_PANEL_ROLES.includes(user.role) && (
            <NavLink to="/admin" className={linkClassName}>
              Admin
            </NavLink>
          )}
        </nav>

        <div className="hidden items-center gap-3 sm:flex">
          <Link
            to="/cart"
            className="relative rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900"
          >
            Cart
            {itemCount > 0 && (
              <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-600 px-1 text-xs font-semibold text-white">
                {itemCount}
              </span>
            )}
          </Link>
          {isAuthenticated ? (
            <>
              <span className="max-w-[10rem] truncate text-sm text-gray-500" title={user?.email}>
                {user?.email}
              </span>
              <Button variant="secondary" size="sm" onClick={() => void handleLogout()}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link to="/login" className="rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">
                Log in
              </Link>
              <Button size="sm" onClick={() => navigate('/register')}>
                Register
              </Button>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 sm:hidden">
          <Link
            to="/cart"
            className="relative rounded-md p-2 text-gray-600 hover:bg-gray-50"
            aria-label={`Cart, ${itemCount} item${itemCount === 1 ? '' : 's'}`}
          >
            <CartIcon />
            {itemCount > 0 && (
              <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-semibold text-white">
                {itemCount}
              </span>
            )}
          </Link>
          <button
            type="button"
            aria-expanded={isMenuOpen}
            aria-controls="mobile-nav-menu"
            aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
            onClick={() => setIsMenuOpen((open) => !open)}
            className="rounded-md p-2 text-gray-600 hover:bg-gray-50"
          >
            <MenuIcon open={isMenuOpen} />
          </button>
        </div>
      </div>

      {isMenuOpen && (
        <nav
          id="mobile-nav-menu"
          aria-label="Primary"
          className="flex flex-col gap-1 border-t border-gray-200 px-4 py-3 sm:hidden"
        >
          <NavLink to="/" end className={linkClassName}>
            Home
          </NavLink>
          <NavLink to="/products" className={linkClassName}>
            Products
          </NavLink>
          {isAuthenticated && (
            <NavLink to="/wishlist" className={linkClassName}>
              Wishlist
            </NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/orders" className={linkClassName}>
              Orders
            </NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/addresses" className={linkClassName}>
              Addresses
            </NavLink>
          )}
          {user && ADMIN_PANEL_ROLES.includes(user.role) && (
            <NavLink to="/admin" className={linkClassName}>
              Admin
            </NavLink>
          )}
          {isAuthenticated ? (
            <>
              <p className="truncate px-3 py-1 text-sm text-gray-500">{user?.email}</p>
              <button
                type="button"
                onClick={() => void handleLogout()}
                className="rounded-md px-3 py-2 text-left text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={linkClassName}>
                Log in
              </NavLink>
              <NavLink to="/register" className={linkClassName}>
                Register
              </NavLink>
            </>
          )}
        </nav>
      )}
    </header>
  )
}

function CartIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 0 0-3 3h15.75m-12.75-3h11.218c1.121-2.3 1.994-4.694 2.602-7.163.075-.3-.155-.587-.465-.587H5.106M7.5 14.25 5.106 5.272M6 18.75a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm12 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
      />
    </svg>
  )
}

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5">
      {open ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5" />
      )}
    </svg>
  )
}
