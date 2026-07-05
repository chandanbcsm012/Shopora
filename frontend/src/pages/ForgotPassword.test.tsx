import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import ForgotPassword from './ForgotPassword'

vi.mock('../api/auth')

const mockedAuth = vi.mocked(authApi)

const GENERIC_MESSAGE = /if an account exists for that email/i

describe('ForgotPassword', () => {
  it('shows the generic success message when the API resolves', async () => {
    mockedAuth.forgotPassword.mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'someone@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByText(GENERIC_MESSAGE)).toBeInTheDocument()
    expect(mockedAuth.forgotPassword).toHaveBeenCalledWith('someone@example.com')
  })

  it('shows the exact same generic message even when the API call fails', async () => {
    mockedAuth.forgotPassword.mockRejectedValue(new ApiError(500, 'INTERNAL_ERROR', 'boom'))
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'nobody@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByText(GENERIC_MESSAGE)).toBeInTheDocument()
    // No error text, no distinct failure UI: an unregistered email or a
    // backend error must look identical to the user.
    expect(screen.queryByText(/boom/i)).not.toBeInTheDocument()
  })
})
