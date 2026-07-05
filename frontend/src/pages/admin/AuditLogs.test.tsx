import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as auditApi from '../../api/audit'
import AuditLogs from './AuditLogs'

vi.mock('../../api/audit')

const mockedAudit = vi.mocked(auditApi)

describe('AuditLogs', () => {
  it('renders the audit log entries returned by the API', async () => {
    mockedAudit.listAuditLogs.mockResolvedValue({
      items: [
        {
          id: 'log-1',
          actor_user_id: 'user-1234-5678',
          action: 'user.invited',
          resource_type: 'user',
          resource_id: 'user-abcd-ef01',
          before_state: null,
          after_state: { role: 'manager' },
          created_at: '2026-07-01T12:00:00Z',
        },
        {
          id: 'log-2',
          actor_user_id: null,
          action: 'user.password_reset_completed',
          resource_type: 'user',
          resource_id: null,
          before_state: null,
          after_state: null,
          created_at: '2026-07-02T09:30:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    })

    render(
      <MemoryRouter>
        <AuditLogs />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('cell', { name: 'user.invited' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'user.password_reset_completed' })).toBeInTheDocument()
    expect(mockedAudit.listAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 }),
    )
  })
})
