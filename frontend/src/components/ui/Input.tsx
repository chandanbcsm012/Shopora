import { forwardRef, useId, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

/**
 * A labeled input that wires up accessibility relationships automatically:
 * `<label htmlFor>`, `aria-invalid`, and `aria-describedby` pointing at
 * whichever of the hint/error text is currently shown. The previous forms
 * nested `<input>` inside `<label>` (which *is* valid a11y-wise) but never
 * associated error text with the field at all, so a screen reader user
 * focused on the input had no way to hear why it was invalid.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, id, className, ...props },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={cn(hintId, errorId).trim() || undefined}
        className={cn(
          'h-10 rounded-md border px-3 text-sm text-gray-900 placeholder:text-gray-400',
          'disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500',
          error ? 'border-danger-600' : 'border-gray-300',
          className,
        )}
        {...props}
      />
      {hint && !error && (
        <p id={hintId} className="text-xs text-gray-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs text-danger-600">
          {error}
        </p>
      )}
    </div>
  )
})
