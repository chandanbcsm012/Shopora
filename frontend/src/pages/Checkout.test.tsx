import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as addressesApi from '../api/addresses'
import * as ordersApi from '../api/orders'
import type { Address } from '../api/types'
import { useCart } from '../context/CartContext'
import Checkout from './Checkout'

vi.mock('../api/addresses')
vi.mock('../api/orders')
vi.mock('../context/CartContext')

const mockedAddresses = vi.mocked(addressesApi)
const mockedOrders = vi.mocked(ordersApi)
const mockedUseCart = vi.mocked(useCart)

const SAMPLE_ADDRESS: Address = {
  id: 'addr-1',
  full_name: 'Jane Doe',
  phone: '555-1234',
  alternate_phone: null,
  company: null,
  address_line1: '123 Main St',
  address_line2: null,
  landmark: null,
  city: 'Springfield',
  district: null,
  state: 'IL',
  country: 'USA',
  postal_code: '62701',
  delivery_instructions: null,
  address_type: 'home',
  is_default_shipping: true,
  is_default_billing: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

function mockCartWithOneItem() {
  mockedUseCart.mockReturnValue({
    cart: {
      id: 'cart-1',
      subtotal_cents: 1999,
      items: [{ id: 'item-1', product_id: 'p1', quantity: 1, unit_price_cents: 1999, line_total_cents: 1999 }],
    },
    productsById: new Map(),
    itemCount: 1,
    isLoading: false,
    error: null,
    addItem: vi.fn(),
    updateItem: vi.fn(),
    removeItem: vi.fn(),
    refreshCart: vi.fn().mockResolvedValue(undefined),
  })
}

function renderCheckout() {
  return render(
    <MemoryRouter>
      <Checkout />
    </MemoryRouter>,
  )
}

describe('Checkout', () => {
  it('disables the place-order button until a shipping address and payment method are selected', async () => {
    const user = userEvent.setup()
    mockCartWithOneItem()
    mockedAddresses.listAddresses.mockResolvedValue([SAMPLE_ADDRESS])

    renderCheckout()

    // Wait for the saved address to load and get auto-selected as shipping.
    await screen.findByText('Jane Doe')
    const placeOrderButton = screen.getByRole('button', { name: 'Place order' })
    expect(placeOrderButton).toBeDisabled()

    await user.click(screen.getByText('Cash on Delivery'))
    expect(placeOrderButton).toBeEnabled()
  })

  it('places an order with the resolved address ids and payment method', async () => {
    const user = userEvent.setup()
    mockCartWithOneItem()
    mockedAddresses.listAddresses.mockResolvedValue([SAMPLE_ADDRESS])
    mockedOrders.checkout.mockResolvedValue({
      id: 'order-1',
      status: 'paid',
      total_cents: 1999,
      currency: 'USD',
      items: [],
      created_at: '2024-01-01T00:00:00Z',
      shipping_address: SAMPLE_ADDRESS,
      billing_address: SAMPLE_ADDRESS,
      payment_status: 'pending',
      invoice_number: null,
    })

    renderCheckout()

    await screen.findByText('Jane Doe')
    await user.click(screen.getByText('Cash on Delivery'))
    await user.click(screen.getByRole('button', { name: 'Place order' }))

    await waitFor(() =>
      expect(mockedOrders.checkout).toHaveBeenCalledWith({
        shipping_address_id: 'addr-1',
        billing_address_id: 'addr-1',
        payment_method: 'cod',
      }),
    )
  })

  it('shows the demo succeed/decline control only for the test-card payment option', async () => {
    const user = userEvent.setup()
    mockCartWithOneItem()
    mockedAddresses.listAddresses.mockResolvedValue([SAMPLE_ADDRESS])

    renderCheckout()

    await screen.findByText('Jane Doe')
    expect(screen.queryByText('Simulate: Succeed')).not.toBeInTheDocument()

    await user.click(screen.getByText('Test Card (demo)'))
    expect(screen.getByText('Simulate: Succeed')).toBeInTheDocument()
    expect(screen.getByText('Simulate: Decline')).toBeInTheDocument()
  })
})
