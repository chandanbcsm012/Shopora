import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status text',
    text: async () => (body === null ? '' : JSON.stringify(body)),
  } as unknown as Response
}

function TestConsumer() {
  const { user, isAuthenticated, login, logout } = useAuth()
  return (
    <div>
      <p data-testid="status">{isAuthenticated ? `logged-in:${user?.email}` : 'logged-out'}</p>
      <button onClick={() => void login('jane@example.com', 'password123')}>Login</button>
      <button onClick={() => void logout()}>Logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input)
        if (url.includes('/auth/login')) {
          return mockResponse(200, { access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' })
        }
        if (url.includes('/auth/me')) {
          return mockResponse(200, {
            id: 'u1',
            email: 'jane@example.com',
            full_name: 'Jane Doe',
            role: 'customer',
            is_active: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          })
        }
        if (url.includes('/auth/logout')) {
          return mockResponse(204, null)
        }
        throw new Error(`Unhandled fetch in test: ${url}`)
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('logs in and exposes the current user, then logs out and clears it', async () => {
    const user = userEvent.setup()
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    expect(screen.getByTestId('status')).toHaveTextContent('logged-out')

    await user.click(screen.getByText('Login'))
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-in:jane@example.com'))

    await user.click(screen.getByText('Logout'))
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-out'))
  })
})
