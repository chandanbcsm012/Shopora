import { useMemo, useState } from 'react'

export interface UsePaginationResult {
  page: number
  setPage: (page: number) => void
  totalPages: number
  goToPrevious: () => void
  goToNext: () => void
}

/**
 * Extracted from the page/totalPages/prev-next logic duplicated across
 * ProductList.tsx and Orders.tsx. Both pages compute
 * `Math.max(1, Math.ceil(total / pageSize))` and clamp prev/next by hand;
 * this hook is the single place that math lives for new (admin) pages.
 * The existing storefront pages are left as-is (already working/tested;
 * not worth the churn for this task).
 */
export function usePagination(total: number, pageSize: number): UsePaginationResult {
  const [page, setPage] = useState(1)
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize])

  function goToPrevious() {
    setPage((p) => Math.max(1, p - 1))
  }

  function goToNext() {
    setPage((p) => Math.min(totalPages, p + 1))
  }

  return { page, setPage, totalPages, goToPrevious, goToNext }
}
