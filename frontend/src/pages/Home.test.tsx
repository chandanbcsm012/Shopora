import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as catalogApi from '../api/catalog'
import { AuthProvider } from '../context/AuthContext'
import { CartProvider } from '../context/CartContext'
import { WishlistProvider } from '../context/WishlistContext'
import Home from './Home'

vi.mock('../api/catalog')

const mockedCatalog = vi.mocked(catalogApi)

function renderHome() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <CartProvider>
          <WishlistProvider>
            <Home />
          </WishlistProvider>
        </CartProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Home', () => {
  it('renders the category showcase, new arrivals, and brand showcase from real API data', async () => {
    mockedCatalog.listCategories.mockResolvedValue([
      { id: 'cat-1', name: 'Widgets', slug: 'widgets', parent_id: null, image_url: null, created_at: '', updated_at: '' },
    ])
    mockedCatalog.listProducts.mockResolvedValue({
      items: [
        {
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
        },
      ],
      total: 1,
      page: 1,
      page_size: 8,
    })
    mockedCatalog.listBrands.mockResolvedValue([
      { id: 'brand-1', name: 'Acme', slug: 'acme', created_at: '', updated_at: '' },
    ])

    renderHome()

    expect(await screen.findByText('Widgets')).toBeInTheDocument()
    expect(await screen.findByText('Blue Widget')).toBeInTheDocument()
    expect(await screen.findByText('Acme')).toBeInTheDocument()

    expect(mockedCatalog.listProducts).toHaveBeenCalledWith(expect.objectContaining({ sort: 'newest' }))
  })

  it('advances to the next hero slide when the "Next slide" control is clicked', async () => {
    mockedCatalog.listCategories.mockResolvedValue([])
    mockedCatalog.listProducts.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 8 })
    mockedCatalog.listBrands.mockResolvedValue([])
    const user = userEvent.setup()

    renderHome()

    const firstHeading = await screen.findByRole('heading', { level: 1 })
    const firstTitle = firstHeading.textContent

    await user.click(screen.getByRole('button', { name: /next slide/i }))

    const secondHeading = await screen.findByRole('heading', { level: 1 })
    expect(secondHeading.textContent).not.toEqual(firstTitle)
  })
})
