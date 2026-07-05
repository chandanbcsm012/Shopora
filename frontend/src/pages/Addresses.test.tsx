import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import * as addressesApi from '../api/addresses'
import type { Address } from '../api/types'
import Addresses from './Addresses'

vi.mock('../api/addresses')

const mockedAddresses = vi.mocked(addressesApi)

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
  is_default_billing: false,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('Addresses', () => {
  it('renders the address list returned by the API', async () => {
    mockedAddresses.listAddresses.mockResolvedValue([SAMPLE_ADDRESS])

    render(<Addresses />)

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('123 Main St')).toBeInTheDocument()
    expect(screen.getByText('Default shipping')).toBeInTheDocument()
    expect(screen.queryByText('Default billing')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no saved addresses', async () => {
    mockedAddresses.listAddresses.mockResolvedValue([])

    render(<Addresses />)

    expect(await screen.findByText('No saved addresses')).toBeInTheDocument()
  })

  it('submits the create-address form and renders the newly created address', async () => {
    const user = userEvent.setup()
    mockedAddresses.listAddresses.mockResolvedValue([])
    mockedAddresses.createAddress.mockResolvedValue({ ...SAMPLE_ADDRESS, id: 'addr-2', full_name: 'New Person' })

    render(<Addresses />)

    const openButtons = await screen.findAllByRole('button', { name: 'Add address' })
    await user.click(openButtons[0])

    await user.type(screen.getByLabelText('Full name'), 'New Person')
    await user.type(screen.getByLabelText('Phone'), '555-0000')
    await user.type(screen.getByLabelText('Address line 1'), '456 Oak Ave')
    await user.type(screen.getByLabelText('City'), 'Springfield')
    await user.type(screen.getByLabelText('State'), 'IL')
    await user.type(screen.getByLabelText('Country'), 'USA')
    await user.type(screen.getByLabelText('Postal code'), '62701')

    await user.click(screen.getByRole('button', { name: 'Add address' }))

    await waitFor(() =>
      expect(mockedAddresses.createAddress).toHaveBeenCalledWith(
        expect.objectContaining({
          full_name: 'New Person',
          phone: '555-0000',
          address_line1: '456 Oak Ave',
          city: 'Springfield',
          state: 'IL',
          country: 'USA',
          postal_code: '62701',
        }),
      ),
    )
    expect(await screen.findByText('New Person')).toBeInTheDocument()
  })
})
