import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as adminApi from '../../api/admin'
import { AuthProvider } from '../../context/AuthContext'
import Users from './Users'

vi.mock('../../api/admin')

const mockedAdmin = vi.mocked(adminApi)

describe('Users', () => {
  it('renders the users returned by the admin API', async () => {
    mockedAdmin.listUsers.mockResolvedValue({
      items: [
        {
          id: 'u1',
          email: 'jane@example.com',
          full_name: 'Jane Doe',
          role: 'admin',
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'u2',
          email: 'bob@example.com',
          full_name: 'Bob Smith',
          role: 'customer',
          is_active: false,
          created_at: '2024-02-01T00:00:00Z',
          updated_at: '2024-02-01T00:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    })

    render(
      <MemoryRouter>
        <AuthProvider>
          <Users />
        </AuthProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('jane@example.com')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.getByText('inactive')).toBeInTheDocument()

    expect(mockedAdmin.listUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20 }))
  })
})
