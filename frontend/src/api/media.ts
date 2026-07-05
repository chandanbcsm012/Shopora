import { apiRequest } from './client'

/**
 * POST /api/v1/media/upload (admin only), multipart/form-data field `file`.
 * Backend validates content-type (image/jpeg|png|webp|gif) and a 5MB size
 * limit, returning UNSUPPORTED_FILE_TYPE (415) / FILE_TOO_LARGE (413) via
 * the standard error envelope otherwise. Returns the URL to store directly
 * on `ProductImage.url` / `Category.image_url` — no separate media library.
 */
export function uploadMedia(file: File): Promise<{ url: string }> {
  const formData = new FormData()
  formData.append('file', file)
  return apiRequest<{ url: string }>('/media/upload', { method: 'POST', body: formData })
}
