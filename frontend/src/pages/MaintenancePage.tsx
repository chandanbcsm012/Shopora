/**
 * Routable at /maintenance, but nothing redirects here automatically — this
 * app has no real health-check/feature-flag system to drive that (and
 * building one would be a separate feature). If a maintenance window is
 * ever needed, this page exists to link/point users to in the meantime.
 */
export default function MaintenancePage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-20 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-gray-900">We'll be back soon</h1>
      <p className="text-sm text-gray-600">
        Shopora is currently undergoing scheduled maintenance. Please check back shortly.
      </p>
      <p className="text-sm text-gray-500">
        Questions? Reach us at [Support Email Address].
      </p>
    </div>
  )
}
