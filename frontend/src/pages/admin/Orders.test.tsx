import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as adminOrdersApi from '../../api/admin-orders'
import AdminOrders from './Orders'

vi.mock('../../api/admin-orders')

const mockedAdminOrders = vi.mocked(adminOrdersApi)

describe('AdminOrders', () => {
  it('renders the orders returned by the admin API', async () => {
    mockedAdminOrders.listAllOrders.mockResolvedValue({
      items: [
        {
          id: 'order-1111111',
          status: 'paid',
          total_cents: 4999,
          currency: 'USD',
          items: [],
          created_at: '2024-01-01T00:00:00Z',
          shipping_address: null,
          billing_address: null,
          payment_status: 'captured',
          invoice_number: 'INV-000001',
        },
        {
          id: 'order-2222222',
          status: 'pending',
          total_cents: 1500,
          currency: 'USD',
          items: [],
          created_at: '2024-02-01T00:00:00Z',
          shipping_address: null,
          billing_address: null,
          payment_status: 'pending',
          invoice_number: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    })

    render(
      <MemoryRouter>
        <AdminOrders />
      </MemoryRouter>,
    )

    expect(await screen.findByText('order-11')).toBeInTheDocument()
    expect(screen.getByText('order-22')).toBeInTheDocument()
    expect(screen.getByText('$49.99')).toBeInTheDocument()
    expect(screen.getByText('$15.00')).toBeInTheDocument()
    expect(screen.getByText('captured')).toBeInTheDocument()

    expect(mockedAdminOrders.listAllOrders).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20 }))
  })

  it('shows an empty state when no orders match the filter', async () => {
    mockedAdminOrders.listAllOrders.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })

    render(
      <MemoryRouter>
        <AdminOrders />
      </MemoryRouter>,
    )

    expect(await screen.findByText('No orders found')).toBeInTheDocument()
  })
})
