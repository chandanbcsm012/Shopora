import { cn } from '../../lib/cn'

/**
 * A shimmer placeholder shaped like the content that's loading, instead of
 * a bare "Loading…" string. This is a perceived-performance win, not a
 * cosmetic one: a layout-matched skeleton tells the user *what kind* of
 * content is coming and *roughly where* it will land, so the page feels
 * like it's already loading rather than blank/stalled.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-md bg-gray-200', className)} />
}
