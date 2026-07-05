import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('reflects the open prop on the underlying <dialog> element', () => {
    const { rerender, container } = render(
      <ConfirmDialog
        open={false}
        title="Delete item?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    const dialog = container.querySelector('dialog')
    expect(dialog?.open).toBe(false)

    rerender(
      <ConfirmDialog open title="Delete item?" onConfirm={() => {}} onCancel={() => {}} />,
    )
    expect(dialog?.open).toBe(true)
    expect(screen.getByText('Delete item?')).toBeInTheDocument()
  })

  it('calls onConfirm when the confirm button is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        open
        title="Delete item?"
        description="This cannot be undone."
        confirmLabel="Delete"
        isDestructive
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    )

    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when the cancel button is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(<ConfirmDialog open title="Delete item?" onConfirm={() => {}} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
