import { Link } from 'react-router-dom'
import { Button } from '../components/ui'

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-20 text-center">
      <p className="text-sm font-semibold text-brand-600">404</p>
      <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Page not found</h1>
      <p className="text-sm text-gray-600">
        The page you're looking for doesn't exist, or may have moved.
      </p>
      <Link to="/" className="mt-2">
        <Button>Back to home</Button>
      </Link>
    </div>
  )
}
