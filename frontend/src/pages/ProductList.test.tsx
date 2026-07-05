import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as catalogApi from '../api/catalog'
import { AuthProvider } from '../context/AuthContext'
import { CartProvider } from '../context/CartContext'
import { WishlistProvider } from '../context/WishlistContext'
import ProductList from './ProductList'

vi.mock('../api/catalog')

const mockedCatalog = vi.mocked(catalogApi)

const SAMPLE_PRODUCTS = [
  {
    id: 'p1',
    name: 'Blue Widget',
    slug: 'blue-widget',
    description: 'A sturdy widget',
    brand_id: null,
    category_id: 'cat-1',
    price_cents: 1999,
    currency: 'USD',
    sku: 'SKU-1',
    stock_quantity: 5,
    is_active: true,
    created_at: '',
    updated_at: '',
  },
  {
    id: 'p2',
    name: 'Red Widget',
    slug: 'red-widget',
    description: 'A vivid widget',
    brand_id: null,
    category_id: 'cat-1',
    price_cents: 2999,
    currency: 'USD',
    sku: 'SKU-2',
    stock_quantity: 0,
    is_active: true,
    created_at: '',
    updated_at: '',
  },
]

function renderProductList() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <CartProvider>
          <WishlistProvider>
            <ProductList />
          </WishlistProvider>
        </CartProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProductList', () => {
  it('renders products returned by the catalog API', async () => {
    mockedCatalog.listCategories.mockResolvedValue([
      { id: 'cat-1', name: 'Widgets', slug: 'widgets', parent_id: null, image_url: null, created_at: '', updated_at: '' },
    ])
    mockedCatalog.listProducts.mockResolvedValue({
      items: SAMPLE_PRODUCTS,
      total: 2,
      page: 1,
      page_size: 12,
    })

    renderProductList()

    expect(await screen.findByText('Blue Widget')).toBeInTheDocument()
    expect(screen.getByText('Red Widget')).toBeInTheDocument()
    expect(screen.getByText('$19.99')).toBeInTheDocument()
    expect(screen.getByText('$29.99')).toBeInTheDocument()

    await waitFor(() =>
      expect(mockedCatalog.listProducts).toHaveBeenCalledWith(expect.objectContaining({ page: 1, sort: 'newest' })),
    )
  })

  it('sends the selected sort option to the API', async () => {
    mockedCatalog.listCategories.mockResolvedValue([])
    mockedCatalog.listProducts.mockResolvedValue({ items: SAMPLE_PRODUCTS, total: 2, page: 1, page_size: 12 })
    const user = userEvent.setup()

    renderProductList()
    await screen.findByText('Blue Widget')

    await user.selectOptions(screen.getByLabelText(/sort by/i), 'price_asc')

    await waitFor(() =>
      expect(mockedCatalog.listProducts).toHaveBeenCalledWith(expect.objectContaining({ sort: 'price_asc' })),
    )
  })

  it('converts the price-range inputs to cents before calling the API', async () => {
    mockedCatalog.listCategories.mockResolvedValue([])
    mockedCatalog.listProducts.mockResolvedValue({ items: SAMPLE_PRODUCTS, total: 2, page: 1, page_size: 12 })
    const user = userEvent.setup()

    renderProductList()
    await screen.findByText('Blue Widget')

    await user.type(screen.getByLabelText(/min price/i), '10')
    await user.type(screen.getByLabelText(/max price/i), '50')

    await waitFor(() =>
      expect(mockedCatalog.listProducts).toHaveBeenCalledWith(
        expect.objectContaining({ min_price_cents: 1000, max_price_cents: 5000 }),
      ),
    )
  })

  it('sends in_stock_only when the checkbox is checked', async () => {
    mockedCatalog.listCategories.mockResolvedValue([])
    mockedCatalog.listProducts.mockResolvedValue({ items: SAMPLE_PRODUCTS, total: 2, page: 1, page_size: 12 })
    const user = userEvent.setup()

    renderProductList()
    await screen.findByText('Blue Widget')

    await user.click(screen.getByLabelText(/in stock only/i))

    await waitFor(() =>
      expect(mockedCatalog.listProducts).toHaveBeenCalledWith(expect.objectContaining({ in_stock_only: true })),
    )
  })

  it('shows a breadcrumb with the active category name when filtered by category', async () => {
    mockedCatalog.listCategories.mockResolvedValue([
      { id: 'cat-1', name: 'Widgets', slug: 'widgets', parent_id: null, image_url: null, created_at: '', updated_at: '' },
    ])
    mockedCatalog.listProducts.mockResolvedValue({ items: SAMPLE_PRODUCTS, total: 2, page: 1, page_size: 12 })
    const user = userEvent.setup()

    renderProductList()
    await screen.findByText('Blue Widget')

    await user.selectOptions(screen.getByLabelText(/category/i), 'cat-1')

    expect(await screen.findByRole('navigation', { name: /breadcrumb/i })).toHaveTextContent('Home/Products/Widgets')
  })
})
