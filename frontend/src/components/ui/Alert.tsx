import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

const TONE_CLASSES = {
  danger: 'border-danger-600/20 bg-danger-50 text-danger-700',
  info: 'border-info-600/20 bg-info-50 text-info-700',
  success: 'border-success-600/20 bg-success-50 text-success-700',
} as const

/**
 * Every page previously rendered errors as a bare `<p className="text-red-600">`
 * with no `role`, so assistive tech had no way to know an error just
 * appeared (it's silent unless the user happens to re-scan the page).
 * `role="alert"` makes screen readers announce it immediately, which is
 * required for WCAG 2.2's status-messages criterion.
 */
export function Alert({ tone = 'danger', children }: { tone?: keyof typeof TONE_CLASSES; children: ReactNode }) {
  return (
    <div role="alert" className={cn('rounded-md border px-3 py-2 text-sm', TONE_CLASSES[tone])}>
      {children}
    </div>
  )
}
