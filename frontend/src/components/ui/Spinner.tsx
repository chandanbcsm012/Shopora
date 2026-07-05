import { cn } from '../../lib/cn'

const SIZE_CLASSES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
} as const

/** A spinner is a decorative loading indicator; the accessible loading
 * state belongs on the element that owns the async action (e.g.
 * `aria-busy` on the button, `role="status"` on a page-level loader), not
 * here, so this stays `aria-hidden` to avoid announcing a meaningless
 * "image" to screen readers on every button. */
export function Spinner({ size = 'md', className }: { size?: keyof typeof SIZE_CLASSES; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block animate-spin rounded-full border-current border-t-transparent',
        SIZE_CLASSES[size],
        className,
      )}
    />
  )
}
