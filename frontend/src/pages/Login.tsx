import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Alert, Button, Card, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto mt-8 max-w-sm sm:mt-16">
      <Card className="p-6">
        <h1 className="mb-6 text-xl font-semibold text-gray-900">Log in</h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Link to="/forgot-password" className="-mt-2 self-end text-sm font-medium text-brand-600 hover:text-brand-700">
            Forgot password?
          </Link>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full">
            {isSubmitting ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
        <p className="mt-6 text-sm text-gray-600">
          No account?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Register
          </Link>
        </p>
      </Card>
    </div>
  )
}
