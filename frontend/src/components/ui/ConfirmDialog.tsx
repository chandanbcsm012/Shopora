import { useEffect, useRef } from 'react'
import { Button } from './Button'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  isDestructive?: boolean
  isConfirming?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * A confirmation modal built on the native `<dialog>` element instead of a
 * hand-rolled overlay + portal + focus-trap implementation: `<dialog
 * open>` via `showModal()` gets us focus trapping, Escape-to-close, and a
 * `::backdrop` for free, from the browser, with zero extra JS and zero new
 * dependencies. We still call `onCancel` on the native `close` event so
 * Escape/backdrop-dismiss stays in sync with the `open` prop the parent
 * owns.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isDestructive = false,
  isConfirming = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    // Feature-detect showModal/close: real browsers all support the native
    // `<dialog>` API, but jsdom (used by the test suite) does not implement
    // showModal()/close() at all as of this writing — only the `open`
    // IDL attribute reflection works there. Falling back to toggling the
    // attribute directly keeps this testable without a dialog polyfill.
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') {
        dialog.showModal()
      } else {
        dialog.setAttribute('open', '')
      }
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') {
        dialog.close()
      } else {
        dialog.removeAttribute('open')
      }
    }
  }, [open])

  return (
    <dialog
      ref={dialogRef}
      onCancel={(e) => {
        // Fires on Escape; prevent the default close so React stays in
        // control of `open`, then let the parent decide (it will set
        // open=false, which closes the dialog via the effect above).
        e.preventDefault()
        onCancel()
      }}
      onClose={onCancel}
      className="m-auto max-w-sm rounded-lg border border-gray-200 bg-white p-0 shadow-popover backdrop:bg-gray-900/40"
    >
      <div className="p-5">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        {description && <p className="mt-2 text-sm text-gray-600">{description}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onCancel} disabled={isConfirming}>
            {cancelLabel}
          </Button>
          <Button
            variant={isDestructive ? 'danger' : 'primary'}
            size="sm"
            onClick={onConfirm}
            isLoading={isConfirming}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
