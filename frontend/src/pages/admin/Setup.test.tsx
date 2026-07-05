import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { AuthProvider } from '../../context/AuthContext'
import Setup from './Setup'

vi.mock('../../api/auth')

const mockedAuth = vi.mocked(authApi)

function renderSetup() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Setup />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Setup', () => {
  it('shows the "already completed" message and a login link when an admin exists', async () => {
    mockedAuth.getBootstrapStatus.mockResolvedValue({ admin_exists: true })

    renderSetup()

    expect(await screen.findByText(/setup already completed/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to login/i })).toHaveAttribute('href', '/login')
    expect(screen.queryByLabelText(/full name/i)).not.toBeInTheDocument()
  })

  it('shows the create-admin form when no admin exists yet', async () => {
    mockedAuth.getBootstrapStatus.mockResolvedValue({ admin_exists: false })

    renderSetup()

    expect(await screen.findByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create admin account/i })).toBeInTheDocument()
  })
})
