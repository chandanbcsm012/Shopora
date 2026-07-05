import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as catalogApi from '../api/catalog'
import * as wishlistApi from '../api/wishlist'
import { useAuth } from './AuthContext'
import { useWishlist, WishlistProvider } from './WishlistContext'

vi.mock('../api/wishlist')
vi.mock('../api/catalog')
vi.mock('./AuthContext')

const mockedWishlistApi = vi.mocked(wishlistApi)
const mockedCatalogApi = vi.mocked(catalogApi)
const mockedUseAuth = vi.mocked(useAuth)

const SAMPLE_PRODUCT = {
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

function authenticated() {
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
}

function unauthenticated() {
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
}

function TestConsumer() {
  const { items, productsById, isWishlisted, toggleWishlist } = useWishlist()
  return (
    <div>
      <p data-testid="count">{items.length}</p>
      <p data-testid="wishlisted-p1">{isWishlisted('p1') ? 'yes' : 'no'}</p>
      <p data-testid="product-name">{productsById.get('p1')?.name ?? ''}</p>
      <button onClick={() => void toggleWishlist('p1')}>Toggle</button>
    </div>
  )
}

describe('WishlistContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches the wishlist and enriches items with product data when authenticated', async () => {
    authenticated()
    mockedWishlistApi.listWishlist.mockResolvedValue([{ id: 'w1', product_id: 'p1', created_at: '' }])
    mockedCatalogApi.getProduct.mockResolvedValue(SAMPLE_PRODUCT)

    render(
      <WishlistProvider>
        <TestConsumer />
      </WishlistProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'))
    expect(await screen.findByTestId('product-name')).toHaveTextContent('Blue Widget')
    expect(screen.getByTestId('wishlisted-p1')).toHaveTextContent('yes')
  })

  it('does not fetch anything while unauthenticated', () => {
    unauthenticated()

    render(
      <WishlistProvider>
        <TestConsumer />
      </WishlistProvider>,
    )

    expect(screen.getByTestId('count')).toHaveTextContent('0')
    expect(mockedWishlistApi.listWishlist).not.toHaveBeenCalled()
  })

  it('adds a product on toggle when not already wishlisted, then refetches the list', async () => {
    authenticated()
    mockedWishlistApi.listWishlist
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 'w1', product_id: 'p1', created_at: '' }])
    mockedWishlistApi.addToWishlist.mockResolvedValue({ id: 'w1', product_id: 'p1', created_at: '' })
    mockedCatalogApi.getProduct.mockResolvedValue(SAMPLE_PRODUCT)
    const user = userEvent.setup()

    render(
      <WishlistProvider>
        <TestConsumer />
      </WishlistProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('wishlisted-p1')).toHaveTextContent('no'))

    await user.click(screen.getByText('Toggle'))

    expect(mockedWishlistApi.addToWishlist).toHaveBeenCalledWith('p1')
    await waitFor(() => expect(screen.getByTestId('wishlisted-p1')).toHaveTextContent('yes'))
  })

  it('removes a product on toggle when already wishlisted, then refetches the list', async () => {
    authenticated()
    mockedWishlistApi.listWishlist
      .mockResolvedValueOnce([{ id: 'w1', product_id: 'p1', created_at: '' }])
      .mockResolvedValueOnce([])
    mockedWishlistApi.removeFromWishlist.mockResolvedValue(undefined)
    mockedCatalogApi.getProduct.mockResolvedValue(SAMPLE_PRODUCT)
    const user = userEvent.setup()

    render(
      <WishlistProvider>
        <TestConsumer />
      </WishlistProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('wishlisted-p1')).toHaveTextContent('yes'))

    await user.click(screen.getByText('Toggle'))

    expect(mockedWishlistApi.removeFromWishlist).toHaveBeenCalledWith('p1')
    await waitFor(() => expect(screen.getByTestId('wishlisted-p1')).toHaveTextContent('no'))
  })

  it('tolerates a 404 for a deleted product instead of crashing', async () => {
    authenticated()
    mockedWishlistApi.listWishlist.mockResolvedValue([{ id: 'w1', product_id: 'p-deleted', created_at: '' }])
    mockedCatalogApi.getProduct.mockRejectedValue(new Error('not found'))

    render(
      <WishlistProvider>
        <TestConsumer />
      </WishlistProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'))
    expect(screen.getByTestId('product-name')).toHaveTextContent('')
  })
})
