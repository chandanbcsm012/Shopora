import { useEffect, useState } from 'react'
import * as auditApi from '../../api/audit'
import type { AuditLog } from '../../api/types'
import { Alert, Card, EmptyState, Skeleton } from '../../components/ui'
import { usePagination } from '../../hooks/usePagination'

const PAGE_SIZE = 20

// Hardcoded from the "Actions to log" list in docs/CONTRACTS.md's audit
// module section — there's no backend endpoint to discover these
// dynamically in this foundation slice.
const ACTIONS = [
  'user.invited',
  'user.invitation_accepted',
  'user.role_changed',
  'user.status_changed',
  'user.password_reset_requested',
  'user.password_reset_completed',
]

// Only `user` resources are logged in this foundation slice.
const RESOURCE_TYPES = ['user']

/** Admin/super_admin only (route-gated by RequireRole in App.tsx). */
export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const { page, setPage, totalPages, goToPrevious, goToNext } = usePagination(total, PAGE_SIZE)
  const [action, setAction] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)
    auditApi
      .listAuditLogs({
        page,
        page_size: PAGE_SIZE,
        action: action || undefined,
        resource_type: resourceType || undefined,
      })
      .then((result) => {
        if (cancelled) return
        setLogs(result.items)
        setTotal(result.total)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load audit logs')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, action, resourceType])

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="audit-action" className="text-sm font-medium text-gray-700">
            Action
          </label>
          <select
            id="audit-action"
            value={action}
            onChange={(e) => {
              setPage(1)
              setAction(e.target.value)
            }}
            className="h-10 rounded-md border border-gray-300 px-3 text-sm"
          >
            <option value="">All actions</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="audit-resource-type" className="text-sm font-medium text-gray-700">
            Resource type
          </label>
          <select
            id="audit-resource-type"
            value={resourceType}
            onChange={(e) => {
              setPage(1)
              setResourceType(e.target.value)
            }}
            className="h-10 rounded-md border border-gray-300 px-3 text-sm"
          >
            <option value="">All resource types</option>
            {RESOURCE_TYPES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {!isLoading && logs.length === 0 && !error && (
        <EmptyState title="No audit log entries" description="Try a different filter." />
      )}

      {!isLoading && logs.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Timestamp</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Resource</th>
                <th className="px-4 py-3 font-medium">Actor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="px-4 py-3 text-gray-500">{new Date(log.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-900">{log.action}</td>
                  <td className="px-4 py-3 text-gray-700">
                    {log.resource_type}
                    {log.resource_id && (
                      <span className="text-gray-500"> &middot; {log.resource_id.slice(0, 8)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {log.actor_user_id ? log.actor_user_id.slice(0, 8) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {!isLoading && logs.length > 0 && totalPages > 1 && (
        <nav aria-label="Audit log pagination" className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={page <= 1}
            onClick={goToPrevious}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600" aria-live="polite">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={goToNext}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </nav>
      )}
    </div>
  )
}
