import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  isLoading?: boolean
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600',
  secondary: 'border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 disabled:bg-white',
  ghost: 'text-gray-700 hover:bg-gray-100 disabled:bg-transparent',
  danger: 'text-danger-600 hover:bg-danger-50 disabled:bg-transparent',
}

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
}

/**
 * The single button implementation for the app. Every page previously
 * hand-rolled its own `rounded bg-gray-900 px-4 py-2 text-white
 * disabled:opacity-50` string — small inconsistencies (some used `rounded`,
 * others effectively needed `rounded-md`) accumulate into a UI that feels
 * assembled rather than designed. One component also gives us one place to
 * fix a11y (disabled + loading semantics) for every button in the app.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', isLoading = false, disabled, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={props.type ?? 'button'}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      {...props}
    >
      {isLoading && <Spinner size="sm" className={variant === 'primary' ? 'text-white' : undefined} />}
      {children}
    </button>
  )
})
