import type { ReactNode } from 'react'

/**
 * A consistent shape for "nothing here" states (empty cart, no orders, no
 * search results) instead of each page picking its own ad hoc bare
 * sentence. Gives every empty state a title, an explanation, and — the
 * part that was missing everywhere before — a way out (the `action` slot).
 */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-gray-300 px-6 py-16 text-center">
      <p className="text-base font-medium text-gray-900">{title}</p>
      {description && <p className="max-w-sm text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
