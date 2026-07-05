import { apiRequest } from './client'
import type { AuditLog, PaginatedResponse } from './types'

export interface ListAuditLogsParams {
  page?: number
  page_size?: number
  action?: string
  resource_type?: string
}

/**
 * GET /api/v1/audit-logs (admin/super_admin only). Paginated, sorted
 * newest-first by the backend, filterable by action/resource_type.
 */
export function listAuditLogs(params: ListAuditLogsParams = {}): Promise<PaginatedResponse<AuditLog>> {
  return apiRequest<PaginatedResponse<AuditLog>>('/audit-logs', { query: { ...params } })
}
