import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Product } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import { ProductCard } from './ProductCard'

vi.mock('../context/AuthContext')
vi.mock('../context/CartContext')
vi.mock('../context/WishlistContext')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseCart = vi.mocked(useCart)
const mockedUseWishlist = vi.mocked(useWishlist)

const PRODUCT: Product = {
  id: 'p1',
  name: 'Blue Widget',
  slug: 'blue-widget',
  description: null,
  brand_id: null,
  category_id: 'cat-1',
  price_cents: 1999,
  currency: 'USD',
  sku: 'SKU-1',
  stock_quantity: 5,
  is_active: true,
  created_at: '',
  updated_at: '',
}

function renderCard() {
  return render(
    <MemoryRouter>
      <ProductCard product={PRODUCT} />
    </MemoryRouter>,
  )
}

describe('ProductCard', () => {
  const addItem = vi.fn().mockResolvedValue(undefined)
  const toggleWishlist = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    addItem.mockResolvedValue(undefined)
    toggleWishlist.mockResolvedValue(undefined)
    mockedUseCart.mockReturnValue({
      cart: null,
      productsById: new Map(),
      itemCount: 0,
      isLoading: false,
      error: null,
      addItem,
      updateItem: vi.fn(),
      removeItem: vi.fn(),
      refreshCart: vi.fn(),
    })
    mockedUseWishlist.mockReturnValue({
      items: [],
      productsById: new Map(),
      isLoading: false,
      error: null,
      isWishlisted: () => false,
      toggleWishlist,
      refreshWishlist: vi.fn(),
    })
  })

  it('shows the product name, price, and stock badge, and disables actions when unauthenticated', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      bootstrap: vi.fn(),
      acceptInvitation: vi.fn(),
      logout: vi.fn(),
    })

    renderCard()

    expect(screen.getByText('Blue Widget')).toBeInTheDocument()
    expect(screen.getByText('$19.99')).toBeInTheDocument()
    expect(screen.getByText('Only 5 left')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /add blue widget to wishlist/i })).toBeDisabled()
  })

  it('adds the product to the cart when authenticated', async () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      bootstrap: vi.fn(),
      acceptInvitation: vi.fn(),
      logout: vi.fn(),
    })
    const user = userEvent.setup()

    renderCard()
    await user.click(screen.getByRole('button', { name: /add to cart/i }))

    expect(addItem).toHaveBeenCalledWith('p1', 1)
  })

  it('reflects wishlisted state and calls toggleWishlist when the heart button is clicked', async () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      bootstrap: vi.fn(),
      acceptInvitation: vi.fn(),
      logout: vi.fn(),
    })
    mockedUseWishlist.mockReturnValue({
      items: [],
      productsById: new Map(),
      isLoading: false,
      error: null,
      isWishlisted: () => true,
      toggleWishlist,
      refreshWishlist: vi.fn(),
    })
    const user = userEvent.setup()

    renderCard()
    const wishlistButton = screen.getByRole('button', { name: /remove blue widget from wishlist/i })
    expect(wishlistButton).toHaveAttribute('aria-pressed', 'true')

    await user.click(wishlistButton)
    expect(toggleWishlist).toHaveBeenCalledWith('p1')
  })

  it('shows "Out of stock" and disables add-to-cart when stock is zero', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      bootstrap: vi.fn(),
      acceptInvitation: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <MemoryRouter>
        <ProductCard product={{ ...PRODUCT, stock_quantity: 0 }} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: /out of stock/i })).toBeDisabled()
  })
})
