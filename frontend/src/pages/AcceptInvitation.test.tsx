import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import { AuthProvider } from '../context/AuthContext'
import AcceptInvitation from './AcceptInvitation'

vi.mock('../api/auth')

const mockedAuth = vi.mocked(authApi)

function renderWithToken(token = 'valid-token') {
  return render(
    <MemoryRouter initialEntries={[`/accept-invitation?token=${token}`]}>
      <AuthProvider>
        <AcceptInvitation />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('AcceptInvitation', () => {
  it('shows the password form with invitation context for a valid token', async () => {
    mockedAuth.getInvitationPreview.mockResolvedValue({
      email: 'newhire@example.com',
      full_name: 'New Hire',
      role: 'manager',
      expires_at: '2026-08-01T00:00:00Z',
    })

    renderWithToken()

    expect(await screen.findByText(/newhire@example.com/i)).toBeInTheDocument()
    expect(screen.getByText(/manager/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /set password/i })).toBeInTheDocument()
    expect(mockedAuth.getInvitationPreview).toHaveBeenCalledWith('valid-token')
  })

  it('shows an alert with the backend error instead of the form for an invalid/expired token', async () => {
    mockedAuth.getInvitationPreview.mockRejectedValue(
      new ApiError(410, 'INVITATION_EXPIRED', 'This invitation has expired'),
    )

    renderWithToken('expired-token')

    expect(await screen.findByRole('alert')).toHaveTextContent(/this invitation has expired/i)
    expect(screen.queryByLabelText(/^password$/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to login/i })).toHaveAttribute('href', '/login')
  })
})
