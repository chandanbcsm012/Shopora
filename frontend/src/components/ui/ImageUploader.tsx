import { useId, useRef, useState } from 'react'
import { uploadMedia } from '../../api/media'
import { ApiError } from '../../api/client'
import { Alert } from './Alert'
import { Spinner } from './Spinner'

export interface ImageUploaderProps {
  value: string | null
  onChange: (url: string | null) => void
  label: string
}

/**
 * A styled file input for the admin image-upload flow: looks like an
 * inviting dashed drop-zone button (no real drag-and-drop wiring — just an
 * `<input type="file">` under a styled `<label>`, per the foundation
 * scope), shows the current value as a thumbnail, an in-progress spinner
 * while `uploadMedia` runs, and surfaces backend validation errors
 * (UNSUPPORTED_FILE_TYPE / FILE_TOO_LARGE) via the shared error envelope.
 */
export function ImageUploader({ value, onChange, label }: ImageUploaderProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Reset so selecting the same file again still fires a change event.
    event.target.value = ''
    if (!file) return

    setError(null)
    setIsUploading(true)
    try {
      const result = await uploadMedia(file)
      onChange(result.url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <div className="flex items-center gap-4">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md bg-gray-100">
          {value ? (
            <img src={value} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="text-[10px] text-gray-400">No image</span>
          )}
        </div>
        <label
          htmlFor={inputId}
          className="flex h-16 flex-1 cursor-pointer items-center justify-center gap-2 rounded-md border-2 border-dashed border-gray-300 px-4 text-sm text-gray-600 hover:border-brand-400 hover:text-brand-600"
        >
          {isUploading ? (
            <>
              <Spinner size="sm" />
              Uploading…
            </>
          ) : (
            <span>{value ? 'Replace image' : 'Click to upload an image'}</span>
          )}
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept="image/*"
          disabled={isUploading}
          onChange={(e) => void handleFileChange(e)}
          className="sr-only"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-sm font-medium text-gray-500 hover:text-danger-600"
          >
            Remove
          </button>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
    </div>
  )
}
