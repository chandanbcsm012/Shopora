import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import type { InvitationPreview } from '../api/types'
import { Alert, Button, Card, Input, Skeleton } from '../components/ui'
import { useAuth } from '../context/AuthContext'

type Status = 'loading' | 'invalid' | 'ready'

/**
 * Public route reached via the emailed invitation link (?token=). Unlike
 * Register.tsx, the password form isn't shown immediately: the token is
 * previewed against GET /auth/invitations/{token} first so we can show who
 * (and what role) is being invited, and surface an invalid/expired/already-
 * accepted error before asking for a password at all.
 */
export default function AcceptInvitation() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const { acceptInvitation } = useAuth()
  const navigate = useNavigate()

  const [status, setStatus] = useState<Status>('loading')
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [preview, setPreview] = useState<InvitationPreview | null>(null)

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!token) {
      setPreviewError('This invitation link is missing a token.')
      setStatus('invalid')
      return
    }
    let cancelled = false
    authApi
      .getInvitationPreview(token)
      .then((result) => {
        if (cancelled) return
        setPreview(result)
        setStatus('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setPreviewError(err instanceof ApiError ? err.message : 'This invitation link is invalid or has expired.')
        setStatus('invalid')
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await acceptInvitation(token, password)
      navigate('/', { replace: true })
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to accept invitation. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto mt-8 max-w-sm sm:mt-16">
      <Card className="p-6">
        <h1 className="mb-6 text-xl font-semibold text-gray-900">Accept invitation</h1>

        {status === 'loading' && (
          <div className="flex flex-col gap-3" role="status">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <span className="sr-only">Checking invitation…</span>
          </div>
        )}

        {status === 'invalid' && (
          <div className="flex flex-col gap-4">
            <Alert>{previewError}</Alert>
            <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Go to login
            </Link>
          </div>
        )}

        {status === 'ready' && preview && (
          <>
            <p className="mb-6 text-sm text-gray-600">
              You&rsquo;ve been invited as <span className="font-medium text-gray-900">{preview.role}</span> —{' '}
              {preview.email}
            </p>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <Input
                label="Password"
                type="password"
                name="password"
                autoComplete="new-password"
                required
                minLength={8}
                hint="At least 8 characters."
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Input
                label="Confirm password"
                type="password"
                name="confirm-password"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
              {formError && <Alert>{formError}</Alert>}
              <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full">
                {isSubmitting ? 'Setting password…' : 'Set password & sign in'}
              </Button>
            </form>
          </>
        )}
      </Card>
    </div>
  )
}
