import { useEffect, useState, type FormEvent } from 'react'
import * as adminApi from '../../api/admin'
import { ApiError } from '../../api/client'
import type { Role, User } from '../../api/types'
import { Alert, Badge, type BadgeTone, Button, Card, ConfirmDialog, EmptyState, Input, Skeleton } from '../../components/ui'
import { usePagination } from '../../hooks/usePagination'
import { useAuth } from '../../context/AuthContext'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 400

const ALL_ROLES: Role[] = ['customer', 'manager', 'admin', 'super_admin']

const ROLE_TONE: Record<Role, BadgeTone> = {
  super_admin: 'danger',
  admin: 'info',
  manager: 'warning',
  customer: 'neutral',
}

/**
 * Mirrors the backend's role hierarchy (docs/CONTRACTS.md) as a UX nicety:
 * super_admin may assign any role; admin may assign manager/customer only
 * (not admin/super_admin); anyone else (shouldn't reach this page at all —
 * it's admin/super_admin gated) gets nothing assignable. The backend is the
 * real enforcement point via INSUFFICIENT_ROLE_PRIVILEGE.
 */
function assignableRoles(currentRole: Role | undefined): Role[] {
  if (currentRole === 'super_admin') return ALL_ROLES
  if (currentRole === 'admin') return ['customer', 'manager']
  return []
}

interface InviteFormState {
  fullName: string
  email: string
  role: Role
  notes: string
}

type PendingAction =
  | { type: 'role'; user: User; nextRole: Role }
  | { type: 'status'; user: User; nextActive: boolean }

export default function Users() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const { page, setPage, totalPages, goToPrevious, goToNext } = usePagination(total, PAGE_SIZE)
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [isConfirming, setIsConfirming] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const assignable = assignableRoles(currentUser?.role)
  const [isInviteFormOpen, setIsInviteFormOpen] = useState(false)
  const [inviteForm, setInviteForm] = useState<InviteFormState>({
    fullName: '',
    email: '',
    role: assignable[0] ?? 'customer',
    notes: '',
  })
  const [isInviting, setIsInviting] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  function openInviteForm() {
    setInviteForm({ fullName: '', email: '', role: assignable[0] ?? 'customer', notes: '' })
    setInviteError(null)
    setIsInviteFormOpen(true)
  }

  function closeInviteForm() {
    setIsInviteFormOpen(false)
    setInviteError(null)
  }

  async function handleInviteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setInviteError(null)
    setInviteSuccess(null)
    setIsInviting(true)
    try {
      const invitation = await adminApi.inviteUser({
        email: inviteForm.email,
        full_name: inviteForm.fullName,
        role: inviteForm.role,
        notes: inviteForm.notes.trim() || undefined,
      })
      setInviteSuccess(`Invitation sent to ${invitation.email}`)
      setIsInviteFormOpen(false)
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : 'Failed to send invitation')
    } finally {
      setIsInviting(false)
    }
  }

  /** Options for a given row's role select: what the current user may
   * assign, plus the row's existing role so the select always has a match
   * (e.g. an admin viewing a super_admin row they can't reassign). */
  function selectableRoles(user: User): Role[] {
    const set = new Set(assignable)
    set.add(user.role)
    return ALL_ROLES.filter((r) => set.has(r))
  }

  useEffect(() => {
    const handle = setTimeout(() => {
      setPage(1)
      setQuery(searchInput.trim())
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setPage identity is stable
  }, [searchInput])

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)
    adminApi
      .listUsers({ page, page_size: PAGE_SIZE, q: query || undefined })
      .then((result) => {
        if (cancelled) return
        setUsers(result.items)
        setTotal(result.total)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load users')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, query])

  function isSelf(user: User): boolean {
    return currentUser?.id === user.id
  }

  async function handleConfirm() {
    if (!pendingAction) return
    setActionError(null)
    setIsConfirming(true)
    try {
      const updated =
        pendingAction.type === 'role'
          ? await adminApi.updateUserRole(pendingAction.user.id, pendingAction.nextRole)
          : await adminApi.updateUserStatus(pendingAction.user.id, pendingAction.nextActive)
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      setPendingAction(null)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to update user')
    } finally {
      setIsConfirming(false)
    }
  }

  function handleCancel() {
    setPendingAction(null)
    setActionError(null)
  }

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5 sm:w-64">
          <label htmlFor="user-search" className="text-sm font-medium text-gray-700">
            Search
          </label>
          <input
            id="user-search"
            type="search"
            placeholder="Search by email or name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="h-10 w-full rounded-md border border-gray-300 px-3 text-sm"
          />
        </div>
        {!isInviteFormOpen && (
          <Button size="sm" onClick={openInviteForm}>
            Invite user
          </Button>
        )}
      </div>

      {isInviteFormOpen && (
        <Card className="mb-6 p-4">
          <h3 className="mb-4 text-sm font-semibold text-gray-900">Invite user</h3>
          <form onSubmit={handleInviteSubmit} className="flex flex-col gap-4">
            <Input
              label="Full name"
              required
              value={inviteForm.fullName}
              onChange={(e) => setInviteForm((prev) => ({ ...prev, fullName: e.target.value }))}
            />
            <Input
              label="Email"
              type="email"
              required
              value={inviteForm.email}
              onChange={(e) => setInviteForm((prev) => ({ ...prev, email: e.target.value }))}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="invite-role" className="text-sm font-medium text-gray-700">
                Role
              </label>
              <select
                id="invite-role"
                value={inviteForm.role}
                onChange={(e) => setInviteForm((prev) => ({ ...prev, role: e.target.value as Role }))}
                className="h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                {assignable.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Notes (optional)"
              value={inviteForm.notes}
              onChange={(e) => setInviteForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
            {inviteError && <Alert>{inviteError}</Alert>}
            <div className="flex gap-2">
              <Button type="submit" isLoading={isInviting}>
                Send invitation
              </Button>
              <Button type="button" variant="secondary" onClick={closeInviteForm} disabled={isInviting}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {inviteSuccess && (
        <div className="mb-4">
          <Alert tone="success">{inviteSuccess}</Alert>
        </div>
      )}

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

      {!isLoading && users.length === 0 && !error && (
        <EmptyState title="No users found" description="Try a different search term." />
      )}

      {!isLoading && users.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Full name</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user) => {
                const self = isSelf(user)
                const selfTitle = self ? 'You cannot modify your own account' : undefined
                return (
                  <tr key={user.id}>
                    <td className="px-4 py-3 text-gray-900">{user.email}</td>
                    <td className="px-4 py-3 text-gray-700">{user.full_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Badge tone={ROLE_TONE[user.role]}>{user.role}</Badge>
                        <select
                          aria-label={`Change role for ${user.email}`}
                          value={user.role}
                          disabled={self}
                          title={selfTitle}
                          onChange={(e) =>
                            setPendingAction({ type: 'role', user, nextRole: e.target.value as Role })
                          }
                          className="h-8 rounded-md border border-gray-300 px-2 text-xs disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
                        >
                          {selectableRoles(user).map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Badge tone={user.is_active ? 'success' : 'neutral'}>
                          {user.is_active ? 'active' : 'inactive'}
                        </Badge>
                        <button
                          type="button"
                          disabled={self}
                          title={selfTitle}
                          onClick={() =>
                            setPendingAction({ type: 'status', user, nextActive: !user.is_active })
                          }
                          className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{new Date(user.created_at).toLocaleDateString()}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}

      {!isLoading && users.length > 0 && totalPages > 1 && (
        <nav aria-label="Users pagination" className="mt-6 flex items-center justify-center gap-3">
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

      <ConfirmDialog
        open={pendingAction !== null}
        title={
          pendingAction?.type === 'role'
            ? `Change role to "${pendingAction.nextRole}"?`
            : pendingAction?.type === 'status'
              ? `${pendingAction.nextActive ? 'Activate' : 'Deactivate'} ${pendingAction.user.email}?`
              : ''
        }
        description={
          actionError ??
          (pendingAction?.type === 'role'
            ? `${pendingAction.user.email}'s role will change from "${pendingAction.user.role}" to "${pendingAction.nextRole}".`
            : undefined)
        }
        confirmLabel={pendingAction?.type === 'status' && !pendingAction.nextActive ? 'Deactivate' : 'Confirm'}
        isDestructive={pendingAction?.type === 'status' && !pendingAction.nextActive}
        isConfirming={isConfirming}
        onConfirm={() => void handleConfirm()}
        onCancel={handleCancel}
      />
    </div>
  )
}
